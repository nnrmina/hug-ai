// Browser speech recognition (Web Speech API, az-AZ): free fallback engine, live captions,
// and hands-free "Bəli / Xeyr" confirmation.

const Recognition = window.SpeechRecognition || window.webkitSpeechRecognition;
export const webSpeechSupported = Boolean(Recognition);

// Recognize one utterance. Returns { promise, stop }. promise → final text ("" if nothing heard).
export function recognizeOnce({ onInterim, lang = "az-AZ", alternatives = 1 } = {}) {
  if (!Recognition) return { promise: Promise.reject(new Error("unsupported")), stop() {} };
  const rec = new Recognition();
  rec.lang = lang;
  rec.interimResults = true;
  rec.maxAlternatives = alternatives;
  rec.continuous = false;

  let finalText = "";
  let lastInterim = "";
  const promise = new Promise((resolve, reject) => {
    rec.onresult = (event) => {
      let interim = "";
      for (let i = event.resultIndex; i < event.results.length; i++) {
        const r = event.results[i];
        if (r.isFinal) finalText += Array.from(r).map((a) => a.transcript).join(" | ");
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
// Elderly speakers answer in many ways ("hə", "hə də", "hı", "olar", "yaxşı", "düzdür"), and the
// recogniser spells short words loosely ("həə", "he", "ha", "hee"), so words are folded to plain
// Latin letters with repeats squeezed before matching.
const fold = (w) => w
  .replace(/ə/g, "e").replace(/ı/g, "i").replace(/ö/g, "o").replace(/ü/g, "u")
  .replace(/ğ/g, "g").replace(/ş/g, "s").replace(/ç/g, "c")
  .replace(/(.)\1+/g, "$1");

const YES = new Set([
  "beli", "bel", "he", "ha", "hehe", "heri", "aha", "eha", "ehe", "ahe", "hede", "hede",
  "oldu", "olar", "olsun", "olsunda", "yaxsi", "yaxsidir", "duzdur", "dogrudur", "duz", "dogru",
  "razi", "raziyam", "elbete", "elbette", "tesdiq", "tesdiqle", "tesdiqleyirem", "tesdiqledim",
  "et", "ele", "elesin", "edin", "zeng", "yarat", "yaradin", "sifaris", "gonder", "gonderin", "ver",
  "isteyirem", "lazimdir", "mumkundur", "yes", "ok", "okey", "okay", "da", "aqa",
]);
const NO = new Set([
  "xeyr", "xeir", "xeyir", "yox", "yoxe", "yo", "yoh", "legv", "istemirem", "lazim", "deyil",
  "dayan", "imtina", "gerekmez", "lazimdeyil", "no", "nope", "olmaz", "etme", "eleme",
]);
const YES_RU = new Set(["да", "ага", "угу", "конечно", "давай", "давайте", "подтверждаю", "хорошо",
  "звони", "позвони", "можно", "ладно", "верно", "правильно", "ок", "окей"]);
const NO_RU = new Set(["нет", "не", "неа", "отмена", "отмени", "стоп", "не надо", "не нужно", "ненадо"]);

export function classifyYesNo(text, lang = "az") {
  const raw = (text || "").toLocaleLowerCase(lang === "ru" ? "ru" : "az");
  if (lang === "ru") {
    const words = raw.split(/[\s,.!?;:|]+/).filter(Boolean);
    if (words.some((w) => NO_RU.has(w))) return "no";
    if (words.some((w) => YES_RU.has(w))) return "yes";
    return null;
  }
  // "hə də" / "he de" spoken as one word, alternatives separated by "|"
  const words = raw.split(/[\s,.!?;:|\-]+/).filter(Boolean).map(fold);
  if (words.some((w) => NO.has(w))) return "no";
  if (words.some((w) => YES.has(w))) return "yes";
  return null;
}

// Listen for one yes/no answer. Returns { promise → "yes" | "no" | null, stop }.
export function listenYesNo(lang = "az") {
  const { promise, stop } = recognizeOnce({ lang: lang === "ru" ? "ru-RU" : "az-AZ", alternatives: 5 });
  return { promise: promise.then((t) => classifyYesNo(t, lang)).catch(() => null), stop };
}
