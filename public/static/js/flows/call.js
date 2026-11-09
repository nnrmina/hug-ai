// Calls open the phone's real dialer (tel:); messages open the SMS composer (sms:) with the
// dictated text pre-filled. The user always presses send/call in the native app.
import { playClip, speak } from "../audio/tts.js";
import { getLang } from "../i18n.js";
import { smsHref, telHref } from "../contacts.js";
import { directCall, isNativeApp } from "../native.js";
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
    directCall(contact.phone_number);
  });
}

export function endCall() {
  clearInterval(timer);
  setText("done-message-subtext", "Zənginiz başa çatdı.");
  showScreen("screen-done");
  const after = playClip("call_end", "Zəng başa çatdı.");
  // A multi-step request continues once the call is over
  import("./assistant.js").then((m) => after.then(() => m.runQueuedStep({ delay: 500 })));
}

export function stopCallTimer() {
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
