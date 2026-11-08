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

function setListeningUi({ badge, quote, mode, showFinish = true, showRetry = false }) {
  if (badge !== undefined) setText("listening-status-badge", badge);
  if (quote !== undefined) setText("recognized-speech-quote", quote);
  if (mode) setMode(mode);
  const finish = document.getElementById("btn-finish-recording");
  const retry = document.getElementById("btn-retry-listening");
  if (finish) finish.hidden = !showFinish;
  if (retry) retry.hidden = !showRetry;
}

export function useServerAudio() {
  return settings.engine !== "browser" && capabilities.audio_understanding && VoiceRecorder.supported;
}

function micError(message) {
  haptic("warning");
  setListeningUi({ badge: "⚠️ Səs eşidilmədi", quote: message, mode: "idle", showFinish: false, showRetry: true });
}

export function cancelListening() {
  if (!active) return;
  active.cancelled = true;
  active.recorder?.cancel();
  active.captions?.stop();
  active = null;
  setMode("idle");
}

export async function startListening() {
  cancelListening();
  stopSpeaking();
  stopConfirmListening();
  cancelPendingAction();
  unlockAudio();
  showScreen("screen-listening");
  setListeningUi({ badge: "🔴 Sizi dinləyirəm...", quote: "Danışın, sizi eşidirəm...", mode: "listening" });
  chime(true);
  haptic("start");

  if (useServerAudio()) return listenWithGemini();
  if (webSpeechSupported) return listenWithBrowser();
  micError("Bu brauzer səs tanımır. Zəhmət olmasa əmri ana səhifədə yazın.");
}

async function listenWithGemini() {
  const session = { kind: "gemini", cancelled: false, hint: "" };
  active = session;

  const recorder = new VoiceRecorder({
    onLevel: setLevel,
    onSpeechStart: () => setText("listening-status-badge", "🎙️ Danışırsınız..."),
    onAutoStop: () => session.finish()
  });
  session.recorder = recorder;

  // Live captions while speaking (desktop / iOS). Android hands the mic to one consumer only.
  if (webSpeechSupported && !isAndroid) {
    try {
      session.captions = recognizeOnce({
        onInterim: (t) => {
          session.hint = t;
          if (t) setText("recognized-speech-quote", `“${t}”`);
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
      micError("Heç nə eşitmədim. Mikrofona yaxın danışın və yenidən cəhd edin.");
      return;
    }
    setListeningUi({ badge: "⏳ Düşünürəm...", mode: "thinking", showFinish: false });
    // give the caption engine a moment to deliver its final words (used as a fallback hint)
    await Promise.race([session.captions?.promise.catch(() => ""), wait(600)]);

    try {
      const data = await sendVoice(result.blob, session.hint);
      if (currentScreen() !== "screen-listening") return; // user navigated away
      handleResponse(data, data.transcript || session.hint);
    } catch (err) {
      if (session.hint) return processText(session.hint, { silentScreen: true });
      micError(err.message || "Serverlə əlaqə qurulmadı.");
    }
  };

  try {
    await recorder.start();
  } catch (err) {
    active = null;
    session.captions?.stop();
    if (err?.name === "NotAllowedError" || err?.name === "SecurityError") {
      micError("Mikrofona icazə verilmədi. Brauzer parametrlərində mikrofona icazə verin.");
    } else if (webSpeechSupported) {
      listenWithBrowser();
    } else {
      micError("Mikrofon işə düşmədi. Əmri yazaraq göndərə bilərsiniz.");
    }
  }
}

async function listenWithBrowser() {
  const session = { kind: "browser", cancelled: false };
  active = session;
  setMode("listening");
  let heard = "";
  session.captions = recognizeOnce({
    onInterim: (t) => {
      heard = t;
      if (t) {
        setText("recognized-speech-quote", `“${t}”`);
        setText("listening-status-badge", "🎙️ Danışırsınız...");
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
    micError(err.code === "not-allowed"
      ? "Mikrofona icazə verilmədi. Brauzer parametrlərində mikrofona icazə verin."
      : "Səs tanınmadı. Yenidən cəhd edin və ya əmri yazın.");
    return;
  }
  if (session.cancelled) return;
  active = null;
  text = (text || heard).trim();
  if (!text) {
    micError("Heç nə eşitmədim. Yenidən cəhd edin.");
    return;
  }
  chime(false);
  processText(text, { silentScreen: true });
}

export function finishListening() {
  active?.finish?.();
}

// Typed or recognized text → agent
export async function processText(text, { silentScreen = false } = {}) {
  text = (text || "").trim();
  if (!text) return;
  stopSpeaking();
  if (!silentScreen) {
    cancelListening();
    cancelPendingAction();
    showScreen("screen-listening");
  }
  setListeningUi({ badge: "⏳ Düşünürəm...", quote: `“${text}”`, mode: "thinking", showFinish: false });
  try {
    const data = await sendText(text);
    handleResponse(data, text);
  } catch (err) {
    micError(err.message || "Serverlə əlaqə qurulmadı.");
    toast(err.message || "Serverlə əlaqə qurulmadı.", { type: "error" });
  }
}

const wait = (ms) => new Promise((r) => setTimeout(r, ms));
