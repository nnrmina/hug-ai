// Routing the agent's reply: confirmation (human-in-the-loop), clarification follow-ups,
// answers, and executing confirmed actions on the device.
import { cancelAction, confirmAction } from "../api.js";
import { playClip, speak, stopSpeaking } from "../audio/tts.js";
import { canListenForAnswer, listenShortAnswer } from "../audio/shortanswer.js";
import { findContact } from "../contacts.js";
import { openReminders } from "../reminders/index.js";
import { capabilities, recordTurn, settings } from "../store.js";
import { haptic } from "../ui/haptics.js";
import { announce, setText, showScreen } from "../ui/screens.js";
import { toast } from "../ui/toast.js";
import { startCall, openSmsComposer } from "./call.js";
import { startOrderTracking, startTaxiTracking } from "./orders.js";
import { processText, startListening } from "./listen.js";
import { getLang, setLang, tr } from "../i18n.js";

let pending = null; // { id, token, type, contact?, order?, message? }
let yesNo = null;
let queuedStep = null; // rest of a multi-step request ("..., sonra qızıma de ki ...")
let queueTimer = null;

export function clearQueuedStep() {
  queuedStep = null;
  clearTimeout(queueTimer);
  document.getElementById("next-step-chip")?.setAttribute("hidden", "");
}

// Run the next step of a multi-step request (after the current one finished)
export function runQueuedStep({ delay = 0 } = {}) {
  if (!queuedStep) return false;
  clearTimeout(queueTimer);
  queueTimer = setTimeout(() => {
    const text = queuedStep;
    clearQueuedStep();
    if (!text) return;
    toast(`${tr("Növbəti addım")}: ${text}`);
    processText(text, { badge: `⏭️ ${tr("Növbəti addım")}...` });
  }, delay);
  return true;
}

// After an answer was spoken: run the next queued step, or (hands-free mode) reopen the mic
export function continueConversation(screenId) {
  if (runQueuedStep({ delay: 600 })) return;
  if (!settings.conversation) return;
  if (screenId && !document.getElementById(screenId)?.classList.contains("active")) return;
  startListening({ followUp: true });
}

function showQueuedChip() {
  const chip = document.getElementById("next-step-chip");
  if (!chip) return;
  if (!queuedStep) return chip.setAttribute("hidden", "");
  chip.querySelector("span").textContent = queuedStep;
  chip.removeAttribute("hidden");
}

export function stopConfirmListening() {
  yesNo?.stop();
  yesNo = null;
}

// Leaving a confirmation without answering cancels it on the server too
export function cancelPendingAction() {
  stopConfirmListening();
  if (!pending) return;
  const { id, token } = pending;
  pending = null;
  cancelAction(id, token).catch(() => {});
}

function updateEngineBadge(engine) {
  const badge = document.getElementById("engine-badge");
  if (!badge || !engine) return;
  const gemini = engine === "gemini";
  badge.hidden = false;
  badge.dataset.engine = engine;
  badge.textContent = gemini ? "✦ Gemini AI" : "Sadə rejim";
  badge.title = gemini ? "Əmrləri Google Gemini başa düşür" : "Süni intellekt əlçatan deyil — əsas əmrlər işləyir";
}

// Speak + show + announce
export function say(text) {
  announce(text);
  return speak(text, getLang());
}

export function showReply({ title, text, heard = "", icon = "✦", tone = "", listenAfter = false }) {
  stopConfirmListening();
  const ru = getLang() === "ru";
  setText("reply-title", tr(title));
  setText("reply-text", text);
  setText("reply-heard", heard ? `${ru ? "Вы" : "Siz"}: “${heard}”` : "");
  const talk = document.getElementById("btn-reply-talk");
  if (talk) talk.lastChild.textContent = tr(listenAfter ? " Cavab verin" : " Yenidən danışın");
  const iconEl = setText("reply-icon", icon);
  if (iconEl) iconEl.className = `reply-icon${tone ? ` ${tone}` : ""}`;
  showScreen("screen-reply");
  say(text).then((finished) => {
    const stillHere = document.getElementById("screen-reply").classList.contains("active");
    if (!finished || !stillHere) return;
    // After a question the mic always opens; otherwise only in hands-free conversation mode
    if (listenAfter) return startListening({ followUp: true });
    continueConversation("screen-reply");
  });
}

function fillConfirm({ badge, title, primary, secondary, yesLabel }) {
  setText("confirm-avatar-badge", badge);
  setText("confirm-question-title", tr(title));
  setText("confirm-details-primary", primary);
  setText("confirm-details-secondary", secondary);
  setText("btn-confirm-yes", tr(yesLabel));
  setText("btn-confirm-cancel", tr("Xeyr, ləğv et"));
}

function askConfirmation(question) {
  const head = document.querySelector("#screen-confirm .center-screen-title");
  if (head) head.textContent = tr("Təsdiqləyin");
  showScreen("screen-confirm");
  haptic("tap");
  const indicator = document.getElementById("confirm-voice-indicator");
  indicator?.classList.remove("listening");

  announce(question);
  // Listen only AFTER the question finished, so the assistant can't hear itself say "Bəli".
  // No "say Bəli" instruction: any natural answer ("hə", "olar", "yox") is understood, and the
  // pulsing mic shows that the assistant is listening.
  speak(question, getLang()).then((finished) => {
    if (!finished || !pending || !canListenForAnswer()) return;
    listenForAnswer(indicator, 2, question);
  });
}

// Up to `tries` listening rounds: a quiet or unclear answer just reopens the mic.
// The reply goes to Gemini when available (works in the Android app and catches "hə").
function listenForAnswer(indicator, tries, question) {
  if (!pending || !document.getElementById("screen-confirm").classList.contains("active")) return;
  indicator?.classList.add("listening");
  yesNo = listenShortAnswer({ question, lang: getLang() });
  yesNo.promise.then(({ answer }) => {
    indicator?.classList.remove("listening");
    if (!pending || !document.getElementById("screen-confirm").classList.contains("active")) return;
    if (answer === "yes") return executeConfirmed();
    if (answer === "no") return cancelConfirmed();
    if (tries > 1) listenForAnswer(indicator, tries - 1, question);
  });
}

export function handleResponse(data, heardText) {
  recordTurn(heardText, data);
  updateEngineBadge(data.engine || capabilities.engine);
  setLang(data.lang);
  pending = null;
  clearQueuedStep();
  if (data.next_step && (data.status === "completed" || data.status === "needs_confirmation")) {
    queuedStep = data.next_step;
  }

  const intent = data.intent;
  const action = data.action_data || {};
  const heard = heardText || data.transcript || "";

  if (data.status === "needs_confirmation") {
    const base = { id: data.action_id, token: data.action_token };

    if (intent === "MAKE_CALL" || intent === "SEND_VOICE_MESSAGE") {
      // Contacts are matched on the device only
      const candidates = [action.contact_alias, ...(action.search_candidates || [])].filter(Boolean);
      const contact = candidates.map(findContact).find(Boolean);
      if (!contact) {
        cancelAction(base.id, base.token).catch(() => {});
        clearQueuedStep();
        const who = action.contact_alias || (getLang() === "ru" ? "Этот человек" : "Bu şəxs");
        return showReply({
          title: "Kontakt tapılmadı",
          text: getLang() === "ru"
            ? `Контакта «${who}» нет в Вашем телефоне. Кому позвонить?`
            : `“${who}” adlı kontakt telefonunuzda yoxdur. Kimə zəng edim?`,
          heard, icon: "?", tone: "muted", listenAfter: true
        });
      }
      if (!contact.real) {
        // Built-in demo contacts carry made-up numbers: dialing them reaches a stranger or nobody
        cancelAction(base.id, base.token).catch(() => {});
        clearQueuedStep();
        return showReply({
          title: getLang() === "ru" ? "Нет номера" : "Nömrə əlavə edilməyib",
          text: getLang() === "ru"
            ? `Сначала добавьте настоящий номер: ${contact.short_name}. Нажмите значок «Семья» вверху.`
            : `${contact.short_name} üçün real nömrə yoxdur. Yuxarıdakı “Ailəm” düyməsindən nömrəni əlavə edin.`,
          heard, icon: "📞", tone: "muted"
        });
      }
      const isCall = intent === "MAKE_CALL";
      pending = { ...base, type: isCall ? "CALL" : "MESSAGE", contact, message: action.message_text || "" };
      const ru = getLang() === "ru";
      const question = ru
        ? `${isCall ? "Позвонить" : "Отправить сообщение"}: ${contact.display_name}?`
        : isCall
          ? `${contact.relation_title} zəng edilsin?`
          : `${contact.relation_title} mesaj göndərilsin?`;
      fillConfirm({
        badge: contact.initial,
        title: question,
        primary: contact.display_name,
        secondary: isCall ? `${getLang() === "ru" ? "Мобильный" : "Mobil"} · ${contact.phone_number}` : `“${action.message_text || heard}”`,
        yesLabel: isCall ? "Bəli, zəng et" : "Bəli, göndər"
      });
      return askConfirmation(question);
    }

    if (intent === "CREATE_REMINDER") {
      pending = { ...base, type: "REMINDER" };
      fillConfirm({
        badge: "⏰",
        title: "Xatırlatma yaradılsın?",
        primary: action.title || "Xatırlatma",
        secondary: formatWhen(action.scheduled_at),
        yesLabel: "Bəli, yarat"
      });
      return askConfirmation(data.response);
    }

    if (intent === "CREATE_MEDICATION") {
      pending = { ...base, type: "MEDICATION" };
      fillConfirm({
        badge: "💊",
        title: "Hər gün xatırladım?",
        primary: action.title || "Dərman",
        secondary: `${getLang() === "ru" ? "Каждый день" : "Hər gün"}: ${(action.med_times || []).join(", ")}`,
        yesLabel: "Bəli, xatırlat"
      });
      return askConfirmation(data.response);
    }

    if (intent === "ORDER_FOOD" || intent === "ORDER_PHARMACY" || intent === "ORDER_TAXI") {
      const order = action.order || {};
      pending = { ...base, type: intent, order };
      const taxi = intent === "ORDER_TAXI";
      fillConfirm({
        badge: order.emoji || "🛍️",
        title: taxi ? "Taksi çağırılsın?" : getLang() === "ru" ? `Заказать в ${order.vendor}?` : `${order.vendor} sifarişi təsdiqlənsin?`,
        primary: order.item || "",
        secondary: `${getLang() === "ru" ? "Итого" : "Cəmi"} ${order.price || ""} · ${order.vendor || "Wolt"}`,
        yesLabel: taxi ? "Bəli, taksi çağır" : "Bəli, sifariş et"
      });
      return askConfirmation(data.response);
    }

    pending = { ...base, type: "GENERAL" };
    fillConfirm({ badge: "✦", title: "Əməliyyat icra edilsin?", primary: `“${heard}”`, secondary: data.response, yesLabel: "Bəli, icra et" });
    return askConfirmation(data.response);
  }

  if (intent === "EMERGENCY") {
    clearQueuedStep();
    return import("../care/care.js").then((m) => m.startSos({ reason: heard }));
  }
  if (intent === "WEATHER" && data.status === "completed") {
    const w = action.weather || {};
    const c = w.code ?? -1;
    const icon = c === 0 ? "☀️" : c <= 3 ? "⛅" : c <= 48 ? "🌫️" : c >= 95 ? "⛈️" : c >= 71 && c <= 86 && !(c >= 80 && c <= 82) ? "❄️" : c >= 51 ? "🌧️" : "🌤️";
    return showReply({ title: "Hava proqnozu", text: data.response, heard, icon });
  }
  if (intent === "OPEN_SCREEN" && data.status === "completed") {
    // "Dərmanlarımı göstər", "Təqvimi aç": open it and say so (no auto-listen: the user is looking)
    const screen = action.screen || "meds";
    if (screen === "reminders") return openReminders(); // reads out the upcoming reminders itself
    say(data.response);
    if (screen === "meds") return import("../care/care.js").then((m) => m.openMeds());
    showScreen("screen-home");
    if (screen === "family") return document.getElementById("contacts-dialog")?.showModal();
    return document.getElementById("btn-open-settings")?.click();
  }
  if (intent === "FIND_PLACE" && data.status === "completed") {
    return import("./places.js").then((m) => m.openPlaces(action.place_type || "pharmacy"));
  }
  if ((intent === "LOG_HEALTH" || intent === "HEALTH_QUERY") && data.status === "completed") {
    import("../care/care.js").then((m) => m.refreshCare());
    const level = action.reading?.level || "normal";
    haptic(level === "normal" ? "success" : "warning");
    return showReply({ title: "Sağlamlıq", text: data.response, heard, icon: "❤️",
                       tone: level === "critical" ? "risk-high" : level === "normal" ? "" : "risk-medium" });
  }
  if (intent === "MEDICATION_TAKEN" || intent === "CHECKIN") {
    import("../care/care.js").then((m) => m.refreshCare());
    haptic("success");
    return showReply({ title: intent === "CHECKIN" ? "Təşəkkürlər" : "Qeyd edildi ✓", text: data.response, heard,
                       icon: intent === "CHECKIN" ? "☀️" : "💊" });
  }

  if (intent === "ANALYZE_MESSAGE") {
    const risk = action.risk_level || "low";
    haptic(risk === "low" ? "success" : "warning");
    return showReply({
      title: risk === "high" ? "Diqqət: fırıldaq riski!" : risk === "medium" ? "Ehtiyatlı olun" : "Təhlükə görünmür",
      text: data.response,
      icon: risk === "low" ? "✓" : "!",
      tone: risk === "high" ? "risk-high" : risk === "medium" ? "risk-medium" : ""
    });
  }
  if (data.status === "rejected") {
    haptic("warning");
    return showReply({ title: "Bunu edə bilmərəm", text: data.response, heard, icon: "✕", tone: "muted" });
  }
  if (data.status === "needs_clarification") {
    const isQuestion = intent !== "UNKNOWN" || action.stt_failed;
    return showReply({
      title: action.stt_failed ? "Eşidə bilmədim" : isQuestion ? "Bir sualım var" : "Başa düşmədim",
      text: data.response,
      heard: action.stt_failed ? "" : heard,
      icon: "?",
      tone: "muted",
      listenAfter: isQuestion
    });
  }
  return showReply({ title: "HUG", text: data.response, heard });
}

export async function executeConfirmed() {
  stopConfirmListening();
  stopSpeaking();
  if (!pending) return;
  const action = pending;
  pending = null;
  haptic("success");

  let result;
  try {
    result = await confirmAction(action.id, action.token);
  } catch (err) {
    haptic("error");
    toast(`Təsdiqlənmədi: ${err.message}`, { type: "error" });
    return showReply({ title: "Xəta baş verdi", text: "Əməliyyat təsdiqlənmədi. Bir az sonra yenidən cəhd edin.", icon: "!", tone: "muted" });
  }

  // Leaving the app (call / SMS) comes last: if more steps are queued, offer them as a chip
  const next = () => runQueuedStep({ delay: 900 });
  const nextOrListen = (finished) => finished !== false && continueConversation("screen-done");
  switch (action.type) {
    case "CALL":
      showQueuedChip();
      return startCall(action.contact);
    case "MESSAGE":
      if (queuedStep) {
        // Opening the SMS app would interrupt the chain: run the next step, keep the SMS for the done screen
        setText("done-message-subtext", `“${action.message}” — ${action.contact.short_name}`);
        showScreen("screen-done");
        return say(result.response).then(next);
      }
      return openSmsComposer(action.contact, action.message, result.response);
    case "ORDER_FOOD":
    case "ORDER_PHARMACY":
      return startOrderTracking(action.order, result.response).then(next);
    case "ORDER_TAXI":
      return startTaxiTracking(action.order, result.response).then(next);
    case "MEDICATION": {
      const care = await import("../care/care.js");
      await care.refreshCare();
      setText("done-message-subtext", result.response);
      showScreen("screen-done");
      say(result.response).then(nextOrListen);
      care.ensureNotifications();
      return;
    }
    case "REMINDER":
      return openReminders({ spoken: result.response, highlightId: result.action_data?.reminder_id,
                             askAlerts: !queuedStep, onSpoken: next });
    default:
      setText("done-message-subtext", result.response);
      showScreen("screen-done");
      say(result.response).then(nextOrListen);
  }
}

export function cancelConfirmed() {
  stopConfirmListening();
  cancelPendingAction();
  clearQueuedStep();
  haptic("tap");
  showScreen("screen-home");
  if (getLang() === "ru") speak("Действие отменено.", "ru");
  else playClip("action_cancel", "Əməliyyat ləğv edildi.");
  toast(getLang() === "ru" ? "Отменено" : "Əməliyyat ləğv edildi");
}

const RU_MONTHS = ["января", "февраля", "марта", "апреля", "мая", "июня", "июля", "августа", "сентября", "октября", "ноября", "декабря"];
const AZ_MONTHS = ["yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avqust", "sentyabr", "oktyabr", "noyabr", "dekabr"];

export function bakuParts(iso) {
  if (!iso) return null;
  const hasZone = /[zZ]|[+-]\d{2}:?\d{2}$/.test(iso);
  const d = new Date(hasZone ? iso : `${iso}+04:00`);
  if (Number.isNaN(d.getTime())) return null;
  const b = new Date(d.getTime() + 4 * 3600 * 1000); // Asia/Baku = UTC+4, no DST
  return { date: d, y: b.getUTCFullYear(), m: b.getUTCMonth(), d: b.getUTCDate(), hh: b.getUTCHours(), mm: b.getUTCMinutes() };
}

export function formatWhen(iso) {
  const p = bakuParts(iso);
  if (!p) return iso || "";
  return `${p.d} ${(getLang() === "ru" ? RU_MONTHS : AZ_MONTHS)[p.m]} · ${String(p.hh).padStart(2, "0")}:${String(p.mm).padStart(2, "0")}`;
}
