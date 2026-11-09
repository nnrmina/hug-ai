// Care features on the elder's phone: SOS, medicines, daily check-in, family circle,
// first-run setup and push subscription.
import {
  addFamily, addHealth, addMedication, removeHealth, careState, doseSnooze, doseTaken, removeFamily, removeMedication,
  saveProfile, sendCheckin, sendSos, subscribeElderPush
} from "../api.js";
import { playClip, speak, stopSpeaking } from "../audio/tts.js";
import { RELATION_OPTIONS, getFamily, setFamily, telHref } from "../contacts.js";
import { ensurePushSubscription, pushSupported } from "../push.js";
import { directCall, isNativeApp, nativeNotificationsReady, onNativeAlarmTap, scheduleMedicineAlarms } from "../native.js";
import { getLocation } from "../location.js";
import { haptic } from "../ui/haptics.js";
import { announce, setText, showScreen } from "../ui/screens.js";
import { toast } from "../ui/toast.js";

let state = null;
let shownDoses = new Set(JSON.parse(sessionStorage.getItem("hug_shown_doses") || "[]"));
const ONB_KEY = "hug_onboarding_done";

const say = (text) => { announce(text); return speak(text); };
const fmtTime = (iso) => {
  const d = new Date(new Date(iso).getTime() + 4 * 3600 * 1000);
  return `${String(d.getUTCHours()).padStart(2, "0")}:${String(d.getUTCMinutes()).padStart(2, "0")}`;
};

// ------------------------------------------------------------------ state
export async function refreshCare() {
  try {
    state = await careState();
  } catch (_) {
    return state;
  }
  setFamily(state.family);
  scheduleMedicineAlarms(state.medications);
  renderCareCard();
  renderFamilySheet();
  if (document.getElementById("screen-meds")?.classList.contains("active")) renderMeds();
  return state;
}

export const careSnapshot = () => state;

function nextDose() {
  if (!state) return null;
  const now = Date.now();
  const open = state.doses.filter((d) => d.status === "pending" || d.status === "missed");
  const due = open.filter((d) => new Date(d.due_at).getTime() <= now + 15 * 60 * 1000);
  return due[0] || open[0] || null;
}

function renderCareCard() {
  const card = document.getElementById("care-card");
  if (!card || !state) return;
  const dose = nextDose();
  const checkinRow = document.getElementById("care-checkin");
  const doseRow = document.getElementById("care-dose");
  checkinRow.hidden = !state.checkin_due;
  doseRow.hidden = !dose;
  if (dose) {
    const due = new Date(dose.due_at).getTime() <= Date.now();
    setText("care-dose-title", `${dose.name}${dose.dose ? " · " + dose.dose : ""}`);
    setText("care-dose-sub", dose.status === "missed" ? `${dose.time} — hələ içilməyib` : due ? `İndi · ${dose.time}` : `Saat ${dose.time}`);
    doseRow.dataset.doseId = dose.id;
    doseRow.classList.toggle("due", due);
  }
  const link = document.getElementById("care-open-meds");
  const total = state.doses.length;
  const taken = state.doses.filter((d) => d.status === "taken").length;
  link.textContent = total ? `Bu gün: ${taken}/${total} dərman içilib →` : "Dərmanlarım →";
  card.hidden = false;
}

// ------------------------------------------------------------------ SOS
let sosTimer = null;
let sosCancelled = false;

export function armSosButton() {
  const btn = document.getElementById("btn-sos");
  if (!btn) return;
  let holdTimer = null;
  const start = (e) => {
    e.preventDefault();
    btn.classList.add("holding");
    haptic("tap");
    holdTimer = setTimeout(() => {
      btn.classList.remove("holding");
      startSos({ reason: "SOS düyməsi" });
    }, 1500);
  };
  const end = () => {
    if (holdTimer) {
      clearTimeout(holdTimer);
      holdTimer = null;
      if (btn.classList.contains("holding")) toast("Təcili kömək üçün SOS düyməsini 2 saniyə basıb saxlayın", { duration: 3500 });
    }
    btn.classList.remove("holding");
  };
  btn.addEventListener("pointerdown", start);
  ["pointerup", "pointerleave", "pointercancel"].forEach((ev) => btn.addEventListener(ev, end));
  btn.addEventListener("keydown", (e) => { if (e.key === "Enter" || e.key === " ") startSos({ reason: "SOS düyməsi" }); });
  document.getElementById("btn-sos-cancel")?.addEventListener("click", cancelSos);
}

export function startSos({ reason = "" } = {}) {
  stopSpeaking();
  sosCancelled = false;
  clearInterval(sosTimer);
  document.getElementById("sos-phase-countdown").hidden = false;
  document.getElementById("sos-phase-sent").hidden = true;
  showScreen("screen-sos");
  haptic("error");
  const locationPromise = getLocation(); // ask for location while counting down
  let left = 5;
  setText("sos-count", String(left));
  say("Ailənizə xəbər verirəm. Ləğv etmək üçün düyməyə toxunun.");
  sosTimer = setInterval(async () => {
    left -= 1;
    setText("sos-count", String(Math.max(left, 0)));
    haptic("tap");
    if (left > 0) return;
    clearInterval(sosTimer);
    if (sosCancelled) return;
    const loc = await locationPromise;
    let result = null;
    try {
      result = await sendSos({ ...(loc || {}), reason });
    } catch (_) { /* still offer the call buttons */ }
    showSosSent(result, Boolean(loc));
  }, 1000);
}

function cancelSos() {
  sosCancelled = true;
  clearInterval(sosTimer);
  haptic("tap");
  showScreen("screen-home");
  playClip("action_cancel", "Əməliyyat ləğv edildi.");
}

function showSosSent(result, hadLocation) {
  document.getElementById("sos-phase-countdown").hidden = true;
  document.getElementById("sos-phase-sent").hidden = false;
  const family = (result?.family || state?.family || []);
  const first = family[0];
  const callBtn = document.getElementById("sos-call-family");
  if (first) {
    callBtn.href = `tel:${first.phone}`;
    setText("sos-call-family-name", `${first.name} — zəng et`);
    callBtn.hidden = false;
  } else {
    callBtn.hidden = true;
  }
  const n = result?.notified_devices ?? 0;
  const sub = !result
    ? "İnternet yoxdur — birbaşa zəng edin."
    : n > 0
      ? `${n} ailə cihazına bildiriş getdi${hadLocation ? ", yeriniz də göndərildi" : ""}.`
      : family.length
        ? "Ailəniz bildirişləri hələ açmayıb — zəng edin."
        : "Ailə üzvü əlavə edilməyib — 103-ə zəng edin.";
  setText("sos-sent-sub", sub);
  haptic("success");
  say(first ? `Xəbər verdim. İndi ${first.name} ilə əlaqə saxlayıram.` : "Xəbər verdim. Lazım olsa 103-ə zəng edin.");
  // Hand off to the dialer automatically when there is someone to call
  if (first) setTimeout(() => directCall(first.phone), 2500);
}

// ------------------------------------------------------------------ medicines
let currentDose = null;

export function showDoseAlert(dose, { speakIt = true } = {}) {
  if (!dose) return;
  currentDose = dose;
  shownDoses.add(dose.id);
  sessionStorage.setItem("hug_shown_doses", JSON.stringify([...shownDoses]));
  setText("dose-name", dose.name);
  setText("dose-meta", `${dose.dose ? dose.dose + " · " : ""}saat ${dose.time}`);
  showScreen("screen-dose");
  haptic("warning");
  if (speakIt) say(`Dərman vaxtıdır: ${dose.name}. İçdinizsə, “içdim” düyməsinə toxunun.`);
}

async function markTaken(id) {
  try {
    await doseTaken(id);
    haptic("success");
    toast("Qeyd edildi ✓ Sağlam olun!", { type: "success" });
    say("Əla, qeyd etdim. Sağlam olun!");
  } catch (err) {
    toast(err.message || "Yadda saxlanmadı", { type: "error" });
  }
  await refreshCare();
}

async function snoozeCurrent() {
  if (!currentDose) return;
  try {
    await doseSnooze(currentDose.id, 10);
    shownDoses.delete(currentDose.id);
    toast("10 dəqiqə sonra yenə xatırladacağam");
    say("Yaxşı, 10 dəqiqə sonra yenə xatırladacağam.");
  } catch (_) {}
  showScreen("screen-home");
  refreshCare();
}

// While the app is open: pop the alert as soon as a dose becomes due
export function watchDoses() {
  setInterval(async () => {
    if (document.visibilityState !== "visible") return;
    await refreshCare();
    const onHome = document.getElementById("screen-home")?.classList.contains("active");
    if (!state || !onHome) return;
    const now = Date.now();
    const due = state.doses.find((d) => d.status === "pending" && !shownDoses.has(d.id) && new Date(d.due_at).getTime() <= now);
    if (due) showDoseAlert(due);
  }, 30000);
}

export function openMeds() {
  showScreen("screen-meds");
  renderMeds();
  refreshCare().then(renderMeds);
}

function renderMeds() {
  renderHealth();
  const doses = document.getElementById("doses-list");
  const meds = document.getElementById("meds-list");
  if (!doses || !meds || !state) return;
  doses.innerHTML = "";
  if (!state.doses.length) {
    doses.innerHTML = '<p class="reminders-empty">Bu gün üçün dərman yoxdur.</p>';
  }
  for (const d of state.doses) {
    const row = document.createElement("div");
    row.className = `reminder-item-card samsung-card dose-row ${d.status}`;
    const label = { taken: "İçilib ✓", missed: "İçilməyib", pending: "Gözləyir" }[d.status] || d.status;
    row.innerHTML = `<div class="reminder-info"><h4></h4><p></p><span class="time-badge"></span></div>`;
    row.querySelector("h4").textContent = `${d.time} · ${d.name}`;
    row.querySelector("p").textContent = d.dose || "";
    row.querySelector(".time-badge").textContent = label;
    if (d.status !== "taken" && new Date(d.due_at).getTime() <= Date.now() + 60 * 60 * 1000) {
      const b = document.createElement("button");
      b.className = "care-taken-btn";
      b.textContent = "İçdim";
      b.addEventListener("click", () => markTaken(d.id).then(renderMeds));
      row.append(b);
    }
    doses.append(row);
  }
  meds.innerHTML = "";
  if (!state.medications.length) meds.innerHTML = '<p class="reminders-empty">Hələ dərman əlavə edilməyib.</p>';
  for (const m of state.medications) {
    const row = document.createElement("div");
    row.className = "reminder-item-card samsung-card";
    row.innerHTML = `<div class="reminder-info"><h4></h4><p></p></div>`;
    row.querySelector("h4").textContent = m.name + (m.dose ? ` · ${m.dose}` : "");
    row.querySelector("p").textContent = "Hər gün: " + m.times.join(", ");
    const del = document.createElement("button");
    del.className = "reminder-action-btn delete";
    del.setAttribute("aria-label", `${m.name} — sil`);
    del.textContent = "✕";
    del.addEventListener("click", async () => {
      await removeMedication(m.id).catch(() => {});
      toast(`“${m.name}” silindi`);
      await refreshCare();
      renderMeds();
    });
    row.append(del);
    meds.append(row);
  }
}

const HEALTH_LABEL = { bp: "Təzyiq", sugar: "Şəkər", pulse: "Nəbz", temp: "Hərarət", weight: "Çəki" };
const HEALTH_LEVEL = { normal: "Normal", high: "Yüksək", low: "Aşağı", critical: "Diqqət!" };

function bakuStamp(iso) {
  const d = new Date(new Date(iso).getTime() + 4 * 3600 * 1000);
  const t = `${String(d.getUTCHours()).padStart(2, "0")}:${String(d.getUTCMinutes()).padStart(2, "0")}`;
  const today = new Date(Date.now() + 4 * 3600 * 1000).toISOString().slice(0, 10);
  return d.toISOString().slice(0, 10) === today ? `bu gün ${t}` : `${d.getUTCDate()}.${String(d.getUTCMonth() + 1).padStart(2, "0")} · ${t}`;
}

function renderHealth() {
  const list = document.getElementById("health-list");
  if (!list || !state) return;
  list.innerHTML = "";
  const items = (state.health || []).slice(0, 5);
  if (!items.length) list.innerHTML = '<p class="reminders-empty">Hələ ölçmə qeyd edilməyib.</p>';
  for (const h of items) {
    const row = document.createElement("div");
    row.className = `reminder-item-card samsung-card health-row ${h.level}`;
    row.innerHTML = `<div class="reminder-info"><h4></h4><p></p><span class="time-badge"></span></div>`;
    row.querySelector("h4").textContent = `${HEALTH_LABEL[h.kind] || h.kind}: ${h.text}`;
    row.querySelector("p").textContent = bakuStamp(h.at);
    row.querySelector(".time-badge").textContent = HEALTH_LEVEL[h.level] || h.level;
    const del = document.createElement("button");
    del.className = "reminder-action-btn delete";
    del.setAttribute("aria-label", `${HEALTH_LABEL[h.kind]} ${h.text} — sil`);
    del.textContent = "✕";
    del.addEventListener("click", async () => {
      await removeHealth(h.id).catch(() => {});
      await refreshCare();
      renderMeds();
    });
    row.append(del);
    list.append(row);
  }
}

function syncHealthForm() {
  const kind = document.getElementById("health-kind")?.value;
  const wrap = document.getElementById("health-value2-wrap");
  const v1 = document.getElementById("health-value");
  if (!wrap || !v1) return;
  wrap.hidden = kind !== "bp";
  document.getElementById("health-value2").required = kind === "bp";
  v1.previousSibling.textContent = kind === "bp" ? "Yuxarı" : "Göstərici";
  v1.placeholder = { bp: "130", sugar: "6.5", pulse: "72", temp: "36.6", weight: "70" }[kind] || "";
}

async function onHealthSubmit(e) {
  e.preventDefault();
  const kind = document.getElementById("health-kind").value;
  const value = parseFloat(document.getElementById("health-value").value.replace(",", "."));
  const v2raw = document.getElementById("health-value2").value;
  const body = { kind, value, ...(kind === "bp" ? { value2: parseFloat(v2raw) } : {}) };
  try {
    const saved = await addHealth(body);
    e.target.reset();
    syncHealthForm();
    toast("Qeyd edildi ✓", { type: "success" });
    if (saved?.reply) say(saved.reply);
  } catch (err) {
    toast(err.message || "Qeyd edilmədi", { type: "error" });
  }
  await refreshCare();
  renderMeds();
}

async function onMedSubmit(e) {
  e.preventDefault();
  const name = document.getElementById("med-name").value.trim();
  const times = document.getElementById("med-times").value.split(/[,\s]+/).map((t) => t.trim()).filter(Boolean);
  if (!name || !times.length) return;
  try {
    await addMedication({ name, times });
    e.target.reset();
    toast("Dərman əlavə edildi ✓", { type: "success" });
    await ensureNotifications();
  } catch (err) {
    toast(err.message || "Əlavə edilmədi", { type: "error" });
  }
  await refreshCare();
  renderMeds();
}

// ------------------------------------------------------------------ check-in
export function showCheckin() {
  const h = new Date(Date.now() + 4 * 3600 * 1000).getUTCHours();
  const greet = h < 12 ? "Sabahınız xeyir!" : h < 18 ? "Günortanız xeyir!" : "Axşamınız xeyir!";
  const name = state?.profile?.name;
  setText("checkin-title", name ? `${greet.replace("!", ",")} ${name}!` : greet);
  showScreen("screen-checkin");
  say(`${greet} Özünüzü necə hiss edirsiniz? Yaxşı, elə də, yoxsa pis?`);
}

async function answerCheckin(mood) {
  haptic(mood === "bad" ? "warning" : "success");
  try {
    await sendCheckin(mood);
  } catch (err) {
    toast(err.message || "Göndərilmədi", { type: "error" });
  }
  await refreshCare();
  const doses = (state?.doses || []).filter((d) => d.status === "pending");
  const plan = doses.length ? ` Bu gün ${doses.length} dərmanınız var: ${doses.map((d) => `saat ${d.time} ${d.name}`).join(", ")}.` : "";
  const reply = {
    good: "Buna çox sevindim!" + plan,
    ok: "Anladım. Özünüzü yorğun hiss etsəniz, dincəlin." + plan,
    bad: "Çox təəssüf. Ailənizə xəbər verdim, sizə zəng edəcəklər."
  }[mood];
  showScreen("screen-home");
  toast(mood === "bad" ? "Ailənizə xəbər verildi" : "Təşəkkürlər! ✓", { type: mood === "bad" ? "info" : "success" });
  say(reply);
}

// ------------------------------------------------------------------ family sheet
function renderFamilySheet() {
  const list = document.getElementById("contacts-list");
  if (!list) return;
  const members = getFamily();
  list.innerHTML = "";
  if (!members.length) {
    list.innerHTML = '<p class="reminders-empty">Hələ ailə üzvü yoxdur. Aşağıdan əlavə edin — təcili halda onlara xəbər gedəcək.</p>';
  }
  for (const c of members) {
    const row = document.createElement("div");
    row.className = "family-row";
    const call = document.createElement("a");
    call.className = "contact-row";
    call.href = telHref(c);
    call.innerHTML = `<span class="contact-avatar" aria-hidden="true"></span><span class="contact-text"><strong></strong><small></small></span><span class="contact-call" aria-hidden="true">📞</span>`;
    call.querySelector(".contact-avatar").textContent = c.initial;
    call.querySelector("strong").textContent = c.display_name;
    call.querySelector("small").textContent = c.phone_number;
    call.setAttribute("aria-label", `${c.display_name} — zəng et`);
    const share = document.createElement("button");
    share.type = "button";
    share.className = "family-share";
    share.textContent = "Keçidi göndər";
    share.setAttribute("aria-label", `${c.short_name} üçün ailə keçidini göndər`);
    share.addEventListener("click", () => shareInvite(c));
    const del = document.createElement("button");
    del.type = "button";
    del.className = "family-del";
    del.setAttribute("aria-label", `${c.short_name} — sil`);
    del.textContent = "✕";
    del.addEventListener("click", async () => {
      await removeFamily(c.id).catch(() => {});
      toast(`${c.short_name} silindi`);
      refreshCare();
    });
    const tools = document.createElement("div");
    tools.className = "family-tools";
    tools.append(share, del);
    row.append(call, tools);
    list.append(row);
  }
}

async function shareInvite(c) {
  const text = `Salam ${c.short_name}! HUG-da mənim ailə dairəmə qoşul: dərmanlarımı, halımı görəcəksən və təcili halda bildiriş alacaqsan. Keçidi aç və “Bildirişləri aç” düyməsinə bas:`;
  try {
    if (navigator.share) {
      await navigator.share({ title: "HUG · Ailə dairəsi", text, url: c.invite_url });
      return;
    }
  } catch (_) { return; }
  try {
    await navigator.clipboard.writeText(`${text} ${c.invite_url}`);
    toast("Keçid kopyalandı — WhatsApp-da göndərin", { type: "success" });
  } catch (_) {
    window.open(`https://wa.me/?text=${encodeURIComponent(`${text} ${c.invite_url}`)}`, "_blank");
  }
}

function fillRelationSelect(select) {
  select.innerHTML = "";
  for (const r of [...RELATION_OPTIONS, "digər"]) {
    const o = document.createElement("option");
    o.value = r === "digər" ? "" : r;
    o.textContent = r[0].toLocaleUpperCase("az") + r.slice(1);
    select.append(o);
  }
}

async function onFamilySubmit(e) {
  e.preventDefault();
  const name = document.getElementById("fam-name").value.trim();
  const relation = document.getElementById("fam-relation").value;
  const phone = document.getElementById("fam-phone").value.trim();
  if (!name || !phone) return;
  try {
    await addFamily({ name, relation, phone });
    e.target.reset();
    toast(`${name} əlavə edildi ✓`, { type: "success" });
  } catch (err) {
    toast(err.message || "Əlavə edilmədi", { type: "error" });
  }
  refreshCare();
}

// ------------------------------------------------------------------ onboarding
function addOnbRow() {
  const wrap = document.getElementById("onb-family");
  const row = document.createElement("div");
  row.className = "onb-row";
  row.innerHTML = `<input type="text" maxlength="100" placeholder="Adı" aria-label="Ailə üzvünün adı" />
    <select aria-label="Kimdir"></select>
    <input type="tel" maxlength="30" placeholder="+994 50 123 45 67" aria-label="Telefon" />`;
  fillRelationSelect(row.querySelector("select"));
  wrap.append(row);
}

export function maybeOnboard() {
  let done = false;
  try { done = localStorage.getItem(ONB_KEY) === "1"; } catch (_) {}
  if (done || !state || state.profile.name || state.family.length) return false;
  document.getElementById("onb-family").innerHTML = "";
  addOnbRow();
  showScreen("screen-onboarding");
  return true;
}

async function onOnboardSubmit(e) {
  e.preventDefault();
  const name = document.getElementById("onb-name").value.trim();
  try {
    if (name) await saveProfile({ name });
    for (const row of document.querySelectorAll("#onb-family .onb-row")) {
      const [n, rel, ph] = [row.children[0].value.trim(), row.children[1].value, row.children[2].value.trim()];
      if (n && ph) await addFamily({ name: n, relation: rel, phone: ph });
    }
  } catch (err) {
    toast(err.message || "Yadda saxlanmadı", { type: "error" });
    return;
  }
  try { localStorage.setItem(ONB_KEY, "1"); } catch (_) {}
  await refreshCare();
  showScreen("screen-home");
  say(name ? `Tanış olmağımıza şadam, ${name}! İndi bildirişlərə icazə verin ki, dərman vaxtını xatırladım.` : "Hazırdır!");
  ensureNotifications();
}

// ------------------------------------------------------------------ notifications
export async function ensureNotifications({ quiet = false } = {}) {
  if (isNativeApp()) {
    const ok = await nativeNotificationsReady();
    if (ok) scheduleMedicineAlarms(state?.medications || []);
    if (!quiet) toast(ok ? "Xatırlatmalar açıqdır 🔔" : "Bildirişlərə icazə verilmədi", { type: ok ? "success" : "error" });
    return ok;
  }
  if (!state?.push?.enabled || !pushSupported()) return false;
  try {
    const r = await ensurePushSubscription(state.push.public_key, subscribeElderPush);
    if (r.ok && !quiet) toast("Bildirişlər açıqdır 🔔", { type: "success" });
    if (!r.ok && r.reason === "denied" && !quiet) toast("Bildirişlər bloklanıb — brauzer ayarlarından açın", { type: "error" });
    return r.ok;
  } catch (_) {
    return false;
  }
}

// ------------------------------------------------------------------ wiring
export function initCare() {
  armSosButton();
  onNativeAlarmTap(async () => {
    await refreshCare();
    const dose = nextDose();
    if (dose && dose.status !== "taken") showDoseAlert(dose);
  });
  document.getElementById("care-checkin")?.addEventListener("click", showCheckin);
  document.getElementById("care-open-meds")?.addEventListener("click", openMeds);
  document.getElementById("care-dose-taken")?.addEventListener("click", (e) => {
    const id = e.currentTarget.closest("[data-dose-id]")?.dataset.doseId;
    if (id) markTaken(id);
  });
  document.getElementById("btn-dose-taken")?.addEventListener("click", async () => {
    if (currentDose) await markTaken(currentDose.id);
    showScreen("screen-home");
  });
  document.getElementById("btn-dose-snooze")?.addEventListener("click", snoozeCurrent);
  document.querySelectorAll(".mood-btn").forEach((b) => b.addEventListener("click", () => answerCheckin(b.dataset.mood)));
  document.getElementById("med-form")?.addEventListener("submit", onMedSubmit);
  document.getElementById("health-form")?.addEventListener("submit", onHealthSubmit);
  document.getElementById("health-kind")?.addEventListener("change", syncHealthForm);
  syncHealthForm();
  document.getElementById("family-form")?.addEventListener("submit", onFamilySubmit);
  fillRelationSelect(document.getElementById("fam-relation"));
  document.getElementById("onb-form")?.addEventListener("submit", onOnboardSubmit);
  document.getElementById("onb-add-row")?.addEventListener("click", addOnbRow);
  document.getElementById("onb-skip")?.addEventListener("click", () => {
    try { localStorage.setItem(ONB_KEY, "1"); } catch (_) {}
    showScreen("screen-home");
  });
}

// Deep links from notifications: /?dose=<id>[&act=taken|snooze], /?checkin=1, /?sos=1
export async function handleCareDeepLink(params) {
  const doseId = params.get("dose");
  if (doseId) {
    await refreshCare();
    const dose = state?.doses.find((d) => d.id === doseId);
    const act = params.get("act");
    if (act === "taken") return markTaken(doseId);
    if (act === "snooze") { currentDose = dose || { id: doseId }; return snoozeCurrent(); }
    if (dose && dose.status !== "taken") return showDoseAlert(dose);
  }
  if (params.get("checkin")) return showCheckin();
  return null;
}

export { fmtTime };
