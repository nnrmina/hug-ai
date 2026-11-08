// Mic-reactive visuals: the listening orb breathes with the voice level and the waveform
// bars follow a smoothed, slightly staggered envelope (driven by the recorder's analyser).

let smoothed = 0;
let phase = 0;
let bars = [];

export function bindWaveform() {
  bars = Array.from(document.querySelectorAll("#audio-waveform .wave-bar"));
}

export function setLevel(level, voiced = false) {
  // fast attack, slow release — feels natural rather than jittery
  smoothed = level > smoothed ? smoothed + (level - smoothed) * 0.55 : smoothed + (level - smoothed) * 0.12;
  phase += 0.22;
  const root = document.getElementById("screen-listening");
  root?.style.setProperty("--level", smoothed.toFixed(3));
  root?.classList.toggle("is-voiced", voiced);
  const n = bars.length;
  bars.forEach((bar, i) => {
    const center = 1 - Math.abs(i - (n - 1) / 2) / (n / 2);
    const wobble = 0.55 + 0.45 * Math.sin(phase + i * 0.9);
    const h = 0.12 + smoothed * (0.35 + 0.65 * center) * wobble;
    bar.style.transform = `scaleY(${Math.min(1, h).toFixed(3)})`;
  });
}

export function setMode(mode) {
  // idle | listening | thinking
  const root = document.getElementById("screen-listening");
  if (!root) return;
  root.dataset.mode = mode;
  if (mode !== "listening") {
    smoothed = 0;
    root.style.setProperty("--level", "0");
    bars.forEach((bar) => { bar.style.transform = ""; });
  }
}
