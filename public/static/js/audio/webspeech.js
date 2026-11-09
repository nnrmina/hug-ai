// Browser speech recognition (Web Speech API, az-AZ): free fallback engine, live captions,
// and hands-free "Bəli / Xeyr" confirmation.

const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
export const webSpeechSupported = Boolean(Recognition);

// Recognize one utterance. Returns { promise, stop }. promise → final text ("" if nothing heard).
export function recognizeOnce({ onInterim, lang = "az-AZ" } = {}) {
  if (!Recognition) return { promise: Promise.reject(new Error("unsupported")), stop() {} };
  const rec = new Recognition();
  rec.lang = lang;
  rec.interimResults = true;
  rec.maxAlternatives = 1;
  rec.continuous = false;

  let finalText = "";
  let lastInterim = "";
  const promise = new Promise((resolve, reject) => {
    rec.onresult = (event) => {
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const r = event.results[i];
        if (r.isFinal) finalText += r[0].transcript;
        else interim += r[0].transcript;
      }
      lastInterim = interim;
      onInterim?.((finalText + " " + interim).trim());
    };
    rec.onerror = (event) => {
      if (event.error === "no-speech" || event.error === "aborted") resolve((finalText || lastInterim).trim());
      else reject(Object.assign(new Error(event.error), { code: event.error }));
    };
    rec.onend = () => resolve((finalText || lastInterim).trim());
  });
  try {
    rec.start();
  } catch (err) {
    return { promise: Promise.reject(err), stop() {} };
  }
  return { promise, stop: () => { try { rec.stop(); } catch (_) {} } };
}

// Word-level yes/no (substring checks matched "he" inside "həkim").
const YES = new Set(["bəli", "beli", "hə", "he", "həri", "heri", "hı", "oldu", "aha", "yes", "ok", "okay",
  "təsdiq", "təsdiqlə", "təsdiqləyirəm", "razıyam", "əlbəttə", "elbette", "olsun", "et", "elə"]);
const NO = new Set(["xeyr", "yox", "ləğv", "legv", "no", "dayan", "lazım", "istəmirəm", "imtina"]);
const YES_RU = new Set(["да", "ага", "конечно", "давай", "подтверждаю", "хорошо", "звони", "можно"]);
const NO_RU = new Set(["нет", "не", "отмена", "отмени", "стоп", "не надо"]);

export function classifyYesNo(text, lang = "az") {
  const words = (text || "").toLocaleLowerCase(lang).split(/[\s,.!?;:]+/).filter(Boolean);
  const [yes, no] = lang === "ru" ? [YES_RU, NO_RU] : [YES, NO];
  if (words.some((w) => no.has(w))) return "no";
  if (words.some((w) => yes.has(w))) return "yes";
  return null;
}

// Listen for one yes/no answer. Returns { promise → "yes" | "no" | null, stop }.
export function listenYesNo(lang = "az") {
  const { promise, stop } = recognizeOnce({ lang: lang === "ru" ? "ru-RU" : "az-AZ" });
  return { promise: promise.then((t) => classifyYesNo(t, lang)).catch(() => null), stop };
}
