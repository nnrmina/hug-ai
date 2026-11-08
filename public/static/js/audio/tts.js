// Speech output: server neural voice (az-AZ-BanuNeural via /api/v1/tts) with the browser's
// own speechSynthesis as fallback, plus a few pre-rendered clips for fixed phrases.
import { ttsUrl } from "../api.js";

const CLIPS = {
  call_end: "/static/audio/call_end.mp3",
  order_done: "/static/audio/order_done.mp3",
  action_cancel: "/static/audio/action_cancel.mp3"
};

let current = null; // { audio, done }
let audioCtx = null;

export function unlockAudio() {
  try {
    if (!audioCtx) {
      const Ctx = window.AudioContext || window.webkitAudioContext;
      if (Ctx) audioCtx = new Ctx();
    }
    if (audioCtx?.state === "suspended") audioCtx.resume();
    if (window.speechSynthesis?.paused) window.speechSynthesis.resume();
  } catch (_) {}
}

export function stopSpeaking() {
  if (current) {
    try { current.audio.pause(); } catch (_) {}
    const done = current.done;
    current = null;
    done?.(true);
  }
  try { window.speechSynthesis?.cancel(); } catch (_) {}
}

export const isSpeaking = () => Boolean(current);

function playUrl(url, fallbackText) {
  return new Promise((resolve) => {
    stopSpeaking();
    const audio = new Audio(url);
    let settled = false;
    const finish = (interrupted = false) => {
      if (settled) return;
      settled = true;
      if (current?.audio === audio) current = null;
      resolve(!interrupted);
    };
    current = { audio, done: finish };
    audio.onended = () => finish(false);
    audio.onerror = () => {
      if (settled || current?.audio !== audio) return;
      current = null;
      settled = true;
      browserSpeak(fallbackText).then(resolve);
    };
    const p = audio.play();
    if (p?.catch) {
      p.catch(() => {
        if (settled || current?.audio !== audio) return;
        current = null;
        settled = true;
        browserSpeak(fallbackText).then(resolve);
      });
    }
  });
}

// Speak an Azerbaijani sentence. Resolves when finished (true) or interrupted (false).
export function speak(text) {
  if (!text) return Promise.resolve(true);
  return playUrl(ttsUrl(text), text);
}

export function playClip(key, fallbackText) {
  const url = CLIPS[key];
  return url ? playUrl(url, fallbackText) : speak(fallbackText);
}

function browserSpeak(text) {
  return new Promise((resolve) => {
    const synth = window.speechSynthesis;
    if (!synth || !text) return resolve(true);
    try {
      synth.cancel();
      const voices = synth.getVoices() || [];
      let voice = voices.find((v) => v.lang?.toLowerCase().startsWith("az"));
      if (!voice) voice = voices.find((v) => v.lang?.toLowerCase().startsWith("tr"));
      // A Turkish voice reads Azerbaijani well enough once "ə" becomes "e"
      const spoken = voice?.lang?.toLowerCase().startsWith("tr") ? text.replace(/ə/g, "e").replace(/Ə/g, "E") : text;
      const u = new SpeechSynthesisUtterance(spoken);
      if (voice) u.voice = voice;
      u.lang = voice?.lang || "tr-TR";
      u.rate = 0.92;
      u.onend = () => resolve(true);
      u.onerror = () => resolve(true);
      synth.speak(u);
    } catch (_) {
      resolve(true);
    }
  });
}

// Short rising two-tone chime when the mic opens
export function chime(up = true) {
  try {
    unlockAudio();
    if (!audioCtx) return;
    const t = audioCtx.currentTime;
    const osc = audioCtx.createOscillator();
    const gain = audioCtx.createGain();
    osc.type = "sine";
    osc.frequency.setValueAtTime(up ? 523.25 : 659.25, t);
    osc.frequency.exponentialRampToValueAtTime(up ? 783.99 : 440, t + 0.14);
    gain.gain.setValueAtTime(0.0001, t);
    gain.gain.exponentialRampToValueAtTime(0.12, t + 0.02);
    gain.gain.exponentialRampToValueAtTime(0.0001, t + 0.3);
    osc.connect(gain).connect(audioCtx.destination);
    osc.start(t);
    osc.stop(t + 0.32);
  } catch (_) {}
}
