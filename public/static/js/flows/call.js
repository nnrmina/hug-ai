// Calls open the phone's real dialer (tel:); messages open the SMS composer (sms:) with the
// dictated text pre-filled. The user always presses send/call in the native app.
import { playClip, speak } from "../audio/tts.js";
import { getLang } from "../i18n.js";
import { smsHref, telHref } from "../contacts.js";
import { directCall, isNativeApp, listSims } from "../native.js";
import { announce, setText, showScreen } from "../ui/screens.js";

let timer = null;
let seconds = 0;

export function startCall(contact) {
  showScreen("screen-calling");
  setText("calling-contact-name", contact.short_name || contact.display_name);
  setText("call-avatar-circle", contact.initial);
  const dialer = document.getElementById("native-dialer-btn");
  if (dialer) dialer.href = telHref(contact);
  clearInterval(timer);
  const ru = getLang() === "ru";

  if (!isNativeApp()) {
    // Browsers (Chrome / Samsung Internet) only open tel: links right after a tap. A voice
    // "Bəli" is no tap, and by the time the spoken line ends the tap has expired, so try at
    // once and otherwise ask the user to press the big call button (a real tap always works).
    document.getElementById("screen-calling")?.classList.add("needs-tap");
    setText("calling-status-timer", ru ? "Нажмите зелёную кнопку, чтобы позвонить" : "Zəng üçün yaşıl düyməyə toxunun");
    directCall(contact.phone_number);
    const line = ru ? `Чтобы позвонить, нажмите зелёную кнопку.` : `Zəng etmək üçün yaşıl düyməyə toxunun.`;
    announce(line);
    speak(line, getLang());
    return;
  }

  document.getElementById("screen-calling")?.classList.remove("needs-tap");
  placeNativeCall(contact, ru);
}

async function placeNativeCall(contact, ru) {
  const callId = ++activeCall;
  // Dual-SIM: ask which SIM instead of leaving it to Android's picker
  let sim;
  const sims = await listSims();
  if (sims.length >= 2) {
    sim = await askSim(sims, ru, callId);
    if (sim === undefined || callId !== activeCall) return; // cancelled or left the screen
  }

  seconds = 0;
  const tick = () => {
    const mm = String(Math.floor(seconds / 60)).padStart(2, "0");
    const ss = String(seconds % 60).padStart(2, "0");
    setText("calling-status-timer", `Zəng edilir... · ${mm}:${ss}`);
    seconds += 1;
  };
  tick();
  timer = setInterval(tick, 1000);

  const line = ru ? `Звоню: ${contact.short_name}.` : `${contact.short_name} ilə əlaqə qurulur.`;
  announce(line);
  speak(line, getLang()).then(() => {
    // Android app: calls directly (the user already said "Bəli")
    if (callId === activeCall) directCall(contact.phone_number, sim);
  });
}

// ---------------------------------------------------------------- SIM choice

let activeCall = 0;
let simListener = null;

const simName = (s, ru) => `SIM ${s.slot}${s.carrier ? ` · ${s.carrier}` : ""}`;
const fold = (w) => w.toLocaleLowerCase("az")
  .replace(/ə/g, "e").replace(/ı/g, "i").replace(/ö/g, "o").replace(/ü/g, "u")
  .replace(/ğ/g, "g").replace(/ş/g, "s").replace(/ç/g, "c");

// "birinci", "bir", "1", "Azercell" → that SIM's index; "yox" / "ləğv" → "cancel"; else null
export function parseSimAnswer(text, sims) {
  const words = fold(text || "").split(/[\s,.!?;:|\-]+/).filter(Boolean);
  if (words.some((w) => ["yox", "xeyr", "legv", "istemirem", "нет", "отмена"].includes(w))) return "cancel";
  const bySlot = (n) => sims.find((s) => s.slot === n)?.index ?? null;
  for (const w of words) {
    if (/^(1|bir|birinci|birinc|birinciden|birinciye|biri|birinden|birden|один|первая|первой|первую)/.test(w)) return bySlot(1);
    if (/^(2|iki|ikinci|ikinciden|ikinciye|ikisi|ikiden|два|вторая|второй|вторую)/.test(w)) return bySlot(2);
  }
  for (const s of sims) {
    const carrier = fold(s.carrier || "").replace(/[^a-z0-9]/g, "");
    if (carrier.length >= 3 && words.some((w) => w.replace(/[^a-z0-9]/g, "").startsWith(carrier.slice(0, 4)))) return s.index; // "azersel" ≈ Azercell
  }
  return null;
}

function askSim(sims, ru, callId) {
  const box = document.getElementById("sim-choice");
  const two = sims.slice(0, 2);
  setText("calling-status-timer", ru ? "С какой SIM-карты позвонить?" : "Hansı SIM-dən zəng edək?");

  return new Promise((resolve) => {
    let done = false;
    const finish = (value) => {
      if (done) return;
      done = true;
      simListener?.stop();
      simListener = null;
      if (box) box.hidden = true;
      resolve(value);
    };

    if (box) {
      box.querySelectorAll(".sim-choice-btn").forEach((btn, i) => {
        const s = two[i];
        btn.hidden = !s;
        if (!s) return;
        btn.textContent = simName(s, ru);
        btn.onclick = () => finish(s.index);
      });
      box.hidden = false;
    }

    const options = two.map((s) => (ru ? `${s.slot === 1 ? "первой" : "второй"}${s.carrier ? `, ${s.carrier}` : ""}` : `${s.slot === 1 ? "birinci" : "ikinci"}${s.carrier ? `, ${s.carrier}` : ""}`));
    const question = ru
      ? `С какой SIM-карты позвонить: ${options.join(", или ")}?`
      : `Hansı SIM-dən zəng edək: ${options.join(", yoxsa ")}?`;
    announce(question);

    const listen = async (tries) => {
      if (done || callId !== activeCall) return finish(undefined);
      // Recorded and transcribed by Gemini when available: browser speech recognition
      // does not work inside the Android app, which is the only place SIMs are listed
      const { canListenForAnswer, listenShortAnswer } = await import("../audio/shortanswer.js");
      if (!canListenForAnswer()) return; // buttons only
      simListener = listenShortAnswer({ question, lang: ru ? "ru" : "az" });
      const { transcript } = await simListener.promise;
      if (done) return;
      const answer = parseSimAnswer(transcript, two);
      if (answer === "cancel") {
        finish(undefined);
        showScreen("screen-home");
        return;
      }
      if (answer !== null) return finish(answer);
      if (tries > 1) listen(tries - 1);
    };
    speak(question, getLang()).then(() => listen(2));
  });
}

export function cancelSimChoice() {
  activeCall += 1;
  simListener?.stop();
  simListener = null;
  const box = document.getElementById("sim-choice");
  if (box) box.hidden = true;
}

export function endCall() {
  cancelSimChoice();
  clearInterval(timer);
  setText("done-message-subtext", "Zənginiz başa çatdı.");
  showScreen("screen-done");
  const after = playClip("call_end", "Zəng başa çatdı.");
  // A multi-step request continues once the call is over
  import("./assistant.js").then((m) => after.then(() => m.runQueuedStep({ delay: 500 })));
}

export function stopCallTimer() {
  cancelSimChoice();
  clearInterval(timer);
}

export function openSmsComposer(contact, message, spoken) {
  setText("done-message-subtext", message ? `“${message}” — ${contact.short_name}` : `Mesaj: ${contact.short_name}`);
  showScreen("screen-done");
  announce(spoken);
  speak(spoken, getLang()).then(() => {
    try { window.location.href = smsHref(contact, message); } catch (_) {}
  });
}
