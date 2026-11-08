// Calls open the phone's real dialer (tel:); messages open the SMS composer (sms:) with the
// dictated text pre-filled. The user always presses send/call in the native app.
import { playClip, speak } from "../audio/tts.js";
import { smsHref, telHref } from "../contacts.js";
import { directCall } from "../native.js";
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
  seconds = 0;
  const tick = () => {
    const mm = String(Math.floor(seconds / 60)).padStart(2, "0");
    const ss = String(seconds % 60).padStart(2, "0");
    setText("calling-status-timer", `Zəng edilir... · ${mm}:${ss}`);
    seconds += 1;
  };
  tick();
  timer = setInterval(tick, 1000);

  announce(`${contact.short_name} ilə əlaqə qurulur`);
  speak(`${contact.short_name} ilə əlaqə qurulur.`).then(() => {
    // Android app: calls directly (the user already said "Bəli"); browser: opens the dialer
    directCall(contact.phone_number);
  });
}

export function endCall() {
  clearInterval(timer);
  setText("done-message-subtext", "Zənginiz başa çatdı.");
  showScreen("screen-done");
  playClip("call_end", "Zəng başa çatdı.");
}

export function stopCallTimer() {
  clearInterval(timer);
}

export function openSmsComposer(contact, message, spoken) {
  setText("done-message-subtext", message ? `“${message}” — ${contact.short_name}` : `Mesaj: ${contact.short_name}`);
  showScreen("screen-done");
  announce(spoken);
  speak(spoken).then(() => {
    try { window.location.href = smsHref(contact, message); } catch (_) {}
  });
}
