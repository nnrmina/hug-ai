// Capturing a command: Gemini mode records audio (WAV) and lets the server transcribe +
// understand it in one call; browser mode uses Web Speech recognition. Typed text goes
// through the same pipeline.
import { sendText, sendVoice } from "../api.js";
import { VoiceRecorder } from "../audio/recorder.js";
import { chime, stopSpeaking, unlockAudio } from "../audio/tts.js";
import { recognizeOnce, webSpeechSupported } from "../audio/webspeech.js";
import { capabilities, settings } from "../store.js";
import { haptic } from "../ui/haptics.js";
import { setLevel, setMode } from "../ui/orb.js";
import { currentScreen, setText, showScreen } from "../ui/screens.js";
import { toast } from "../ui/toast.js";
import { cancelPendingAction, handleResponse, stopConfirmListening } from "./assistant.js";

const isAndroid = /Android/i.test(navigator.userAgent);
let active = null; // { kind, recorder?, captions?, finish, cancelled }

// Minimal listening screen: no instruction texts. The card stays hidden until there is something
// to show — the user's own words, or a one-line error. The badge is screen-reader only.
function showQuote(text, { error = false } = {}) {
  setText("recognized-speech-quote", text || "");
  const card = document.getElementById("transcript-card");
  if (!card) return;
  card.hidden = !text;
  card.classList.toggle("is-error", Boolean(text) && error);
}

function setListeningUi({ badge, quote, mode, showFinish = true, showRetry = false, error = false }) {
  if (badge !== undefined) setText("listening-status-badge", badge);
  if (quote !== undefined) showQuote(quote, { error });
  if (mode) setMode(mode);
  const finish = document.getElementById("btn-finish-recording");
  const retry = document.getElementById("btn-retry-listening");
  if (finish) finish.hidden = !showFinish;
  if (retry) retry.hidden = !showRetry;
}

export function useServerAudio() {
  return settings.engine !== "browser" && capabilities.audio_understanding && VoiceRecorder.supported;
}

function micError(message = "Eşitmədim") {
  haptic("warning");
  setListeningUi({ badge: message, quote: message, mode: "idle", showFinish: false, showRetry: true, error: true });
}

export function cancelListening() {
  if (!active) return;
  active.cancelled = true;
  active.recorder?.cancel();
  active.captions?.stop();
  active = null;
  setMode("idle");
}

// followUp: opened automatically after an answer (hands-free conversation). If the user
// says nothing, we end quietly instead of showing an error.
export async function startListening({ followUp = false } = {}) {
  cancelListening();
  stopSpeaking();
  stopConfirmListening();
  cancelPendingAction();
  unlockAudio();
  showScreen("screen-listening");
  setListeningUi({
    badge: "Dinləyirəm",
    quote: "",
    mode: "listening"
  });
  chime(true);
  if (!followUp) haptic("start");

  if (useServerAudio()) return listenWithGemini(followUp);
  if (webSpeechSupported) return listenWithBrowser(followUp);
  micError("Bu brauzer səsi tanımır");
}

// Hands-free follow-up heard nothing: close the conversation quietly
function endFollowUp() {
  setMode("idle");
  chime(false);
  showScreen("screen-home");
  toast("Danışmaq üçün mikrofona toxunun", { duration: 2200 });
}

async function listenWithGemini(followUp = false) {
  const session = { kind: "gemini", cancelled: false, hint: "", followUp };
  active = session;

  const recorder = new VoiceRecorder({
    onLevel: setLevel,
    onSpeechStart: () => setText("listening-status-badge", "Danışırsınız"),
    onAutoStop: () => session.finish()
  });
  session.recorder = recorder;

  // Live captions while speaking (desktop / iOS). Android hands the mic to one consumer only.
  if (webSpeechSupported && !isAndroid) {
    try {
      session.captions = recognizeOnce({
        onInterim: (t) => {
          session.hint = t;
          if (t) showQuote(`“${t}”`);
        }
      });
      session.captions.promise.then((t) => { if (t) session.hint = t; }).catch(() => {});
    } catch (_) { session.captions = null; }
  }

  let finishing = false;
  session.finish = async () => {
    if (finishing || session.cancelled) return;
    finishing = true;
    const result = await recorder.stop();
    session.captions?.stop();
    if (session.cancelled) return;
    active = null;
    chime(false);

    if (!result || !result.hadSpeech) {
      if (session.followUp && !session.hint) return endFollowUp();
      micError();
      return;
    }
    setListeningUi({ badge: "Düşünürəm", mode: "thinking", showFinish: false });
    // give the caption engine a moment to deliver its final words (used as a fallback hint)
    await Promise.race([session.captions?.promise.catch(() => ""), wait(600)]);

    try {
      const data = await sendVoice(result.blob, session.hint);
      if (currentScreen() !== "screen-listening") return; // user navigated away
      handleResponse(data, data.transcript || session.hint);
    } catch (err) {
      if (session.hint) return processText(session.hint, { silentScreen: true });
      micError("Bağlantı yoxdur");
    }
  };

  try {
    await recorder.start();
  } catch (err) {
    active = null;
    session.captions?.stop();
    if (err?.name === "NotAllowedError" || err?.name === "SecurityError") {
      micError("Mikrofona icazə verin");
    } else if (webSpeechSupported) {
      listenWithBrowser();
    } else {
      micError("Mikrofon işləmir");
    }
  }
}

async function listenWithBrowser(followUp = false) {
  const session = { kind: "browser", cancelled: false };
  active = session;
  setMode("listening");
  let heard = "";
  session.captions = recognizeOnce({
    onInterim: (t) => {
      heard = t;
      if (t) {
        showQuote(`“${t}”`);
        setText("listening-status-badge", "Danışırsınız");
        setLevel(0.55, true);
      }
    }
  });
  session.finish = () => session.captions.stop();

  let text = "";
  try {
    text = await session.captions.promise;
  } catch (err) {
    if (session.cancelled) return;
    active = null;
    micError(err.code === "not-allowed" ? "Mikrofona icazə verin" : "Eşitmədim");
    return;
  }
  if (session.cancelled) return;
  active = null;
  text = (text || heard).trim();
  if (!text) {
    if (followUp) return endFollowUp();
    micError();
    return;
  }
  chime(false);
  processText(text, { silentScreen: true });
}

export function finishListening() {
  active?.finish?.();
}

// Typed or recognized text → agent
export async function processText(text, { silentScreen = false, badge = "Düşünürəm" } = {}) {
  text = (text || "").trim();
  if (!text) return;
  stopSpeaking();
  if (!silentScreen) {
    cancelListening();
    cancelPendingAction();
    showScreen("screen-listening");
  }
  setListeningUi({ badge, quote: `“${text}”`, mode: "thinking", showFinish: false });
  try {
    const data = await sendText(text);
    handleResponse(data, text);
  } catch (err) {
    micError("Bağlantı yoxdur");
    toast(err.message || "Serverlə əlaqə qurulmadı.", { type: "error" });
  }
}

const wait = (ms) => new Promise((r) => setTimeout(r, ms));
