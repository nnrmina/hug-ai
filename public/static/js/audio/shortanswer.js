// Listening for a short spoken reply: "hə / yox" on the confirm screen, "birinci / ikinci" for
// the SIM choice.
//
// When the server understands audio (Gemini), the reply is recorded and sent there: browser
// speech recognition does not work inside the Android app (WebView) and often misses
// one-syllable words like "hə" in Chrome. Otherwise browser recognition is used.
import { sendShortAnswer } from "../api.js";
import { capabilities, settings } from "../store.js";
import { VoiceRecorder } from "./recorder.js";
import { classifyYesNo, recognizeOnce, webSpeechSupported } from "./webspeech.js";

const serverAudio = () => settings.engine !== "browser" && capabilities.audio_understanding && VoiceRecorder.supported;

export const canListenForAnswer = () => serverAudio() || webSpeechSupported;

// → { promise: Promise<{ transcript, answer: "yes" | "no" | null }>, stop }
// promise resolves with transcript "" and answer null when nothing usable was heard.
export function listenShortAnswer({ question = "", lang = "az", onLevel } = {}) {
  const empty = { transcript: "", answer: null };
  if (serverAudio()) return listenWithServer({ question, lang, onLevel, empty });
  if (!webSpeechSupported) return { promise: Promise.resolve(empty), stop() {} };
  const { promise, stop } = recognizeOnce({ lang: lang === "ru" ? "ru-RU" : "az-AZ", alternatives: 5 });
  return {
    promise: promise
      .then((t) => ({ transcript: t, answer: classifyYesNo(t, lang) }))
      .catch(() => empty),
    stop
  };
}

function listenWithServer({ question, lang, onLevel, empty }) {
  let stopped = false;
  let finish = () => {};
  const recorder = new VoiceRecorder({
    onLevel: onLevel || (() => {}),
    onAutoStop: () => finish()
  });

  const promise = new Promise((resolve) => {
    let finishing = false;
    finish = async () => {
      if (finishing) return;
      finishing = true;
      const result = await recorder.stop().catch(() => null);
      if (stopped || !result || !result.hadSpeech) return resolve(empty);
      try {
        const data = await sendShortAnswer(result.blob, { question });
        const transcript = (data?.transcript || "").trim();
        // the server's yes/no, double-checked with the same word rules used offline
        const answer = data?.answer === "yes" || data?.answer === "no" ? data.answer : classifyYesNo(transcript, lang);
        resolve({ transcript, answer });
      } catch (_) {
        resolve(empty);
      }
    };
    recorder.start()
      .then(() => { if (stopped) recorder.cancel(); }) // stopped while the mic was opening
      .catch(() => resolve(empty)); // mic refused / busy
  });

  return {
    promise,
    stop: () => {
      stopped = true;
      recorder.cancel();
      finish();
    }
  };
}
