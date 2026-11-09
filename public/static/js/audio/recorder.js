// Microphone capture → 16 kHz mono WAV, with live level metering and voice-activity
// detection (auto-stop after the user stops talking).
//
// Why WAV: Gemini's audio input lists wav/mp3/aac/ogg/flac — not the webm/opus Chrome's
// MediaRecorder produces, nor Safari's mp4. Raw PCM captured via AudioWorklet works on
// every browser and is tiny at 16 kHz (32 KB/s; 15 s ≈ 480 KB).

const TARGET_RATE = 16000;
const MAX_MS = 15000;
const NO_SPEECH_MS = 7000;
const END_SILENCE_MS = 1300;
const CALIBRATE_MS = 350;

const WORKLET_SRC = `
class PcmTap extends AudioWorkletProcessor {
  process(inputs) {
    const ch = inputs[0] && inputs[0][0];
    if (ch) this.port.postMessage(ch.slice(0));
    return true;
  }
}
registerProcessor("pcm-tap", PcmTap);
`;

export class VoiceRecorder {
  constructor({ onLevel, onSpeechStart, onAutoStop } = {}) {
    this.onLevel = onLevel || (() => {});
    this.onSpeechStart = onSpeechStart || (() => {});
    this.onAutoStop = onAutoStop || (() => {});
    this.chunks = [];
    this.running = false;
  }

  static get supported() {
    return Boolean(navigator.mediaDevices?.getUserMedia && (window.AudioContext || window.webkitAudioContext));
  }

  async start() {
    this.stream = await navigator.mediaDevices.getUserMedia({
      audio: { echoCancellation: true, noiseSuppression: true, autoGainControl: true, channelCount: 1 }
    });
    const Ctx = window.AudioContext || window.webkitAudioContext;
    this.ctx = new Ctx();
    if (this.ctx.state === "suspended") await this.ctx.resume();
    this.sampleRate = this.ctx.sampleRate;
    this.source = this.ctx.createMediaStreamSource(this.stream);

    this.analyser = this.ctx.createAnalyser();
    this.analyser.fftSize = 1024;
    this.source.connect(this.analyser);
    this.levelBuf = new Float32Array(this.analyser.fftSize);

    const sink = this.ctx.createGain();
    sink.gain.value = 0; // keep the graph pulling without echoing the mic to the speaker
    sink.connect(this.ctx.destination);

    if (this.ctx.audioWorklet) {
      const url = URL.createObjectURL(new Blob([WORKLET_SRC], { type: "application/javascript" }));
      await this.ctx.audioWorklet.addModule(url);
      URL.revokeObjectURL(url);
      this.tap = new AudioWorkletNode(this.ctx, "pcm-tap");
      this.tap.port.onmessage = (e) => this.running && this.chunks.push(e.data);
    } else {
      // Old Safari: deprecated but universally available
      this.tap = this.ctx.createScriptProcessor(4096, 1, 1);
      this.tap.onaudioprocess = (e) => this.running && this.chunks.push(e.inputBuffer.getChannelData(0).slice(0));
    }
    this.source.connect(this.tap);
    this.tap.connect(sink);

    this.running = true;
    this.startedAt = performance.now();
    this.speechStartedAt = null;
    this.lastVoiceAt = null;
    this.noiseFloor = 0.004;
    this.calibration = [];
    this._loop();
  }

  _rms() {
    this.analyser.getFloatTimeDomainData(this.levelBuf);
    let sum = 0;
    for (let i = 0; i < this.levelBuf.length; i++) sum += this.levelBuf[i] * this.levelBuf[i];
    return Math.sqrt(sum / this.levelBuf.length);
  }

  _loop() {
    if (!this.running) return;
    const now = performance.now();
    const elapsed = now - this.startedAt;
    const rms = this._rms();

    if (elapsed < CALIBRATE_MS) {
      this.calibration.push(rms);
    } else if (this.calibration.length) {
      const sorted = this.calibration.sort((a, b) => a - b);
      this.noiseFloor = Math.max(0.003, sorted[Math.floor(sorted.length / 2)]);
      this.calibration = [];
    }

    const threshold = Math.max(0.018, this.noiseFloor * 3.2);
    const voiced = elapsed >= CALIBRATE_MS && rms > threshold;
    if (voiced) {
      if (!this.speechStartedAt) {
        this.speechStartedAt = now;
        this.onSpeechStart();
      }
      this.lastVoiceAt = now;
    }

    // perceptual level 0..1 for the orb / waveform
    this.onLevel(Math.min(1, Math.max(0, (rms - this.noiseFloor) / 0.12)), voiced);

    let reason = null;
    if (elapsed > MAX_MS) reason = "max";
    else if (!this.speechStartedAt && elapsed > NO_SPEECH_MS) reason = "no-speech";
    else if (this.speechStartedAt && now - this.lastVoiceAt > END_SILENCE_MS) reason = "silence";

    if (reason) {
      this.onAutoStop(reason);
      return;
    }
    // A timer, not requestAnimationFrame: rAF stops when the page is hidden (screen locked,
    // app in background), which would leave the microphone open forever.
    this.raf = setTimeout(() => this._loop(), 50);
  }

  get hadSpeech() {
    return Boolean(this.speechStartedAt);
  }

  // Stop and return { blob, durationMs, hadSpeech }
  async stop() {
    if (!this.running) return null;
    this.running = false;
    clearTimeout(this.raf);
    const durationMs = performance.now() - this.startedAt;
    try { this.source.disconnect(); } catch (_) {}
    try { this.tap.disconnect(); } catch (_) {}
    this.stream.getTracks().forEach((t) => t.stop());
    try { await this.ctx.close(); } catch (_) {}

    const pcm = concat(this.chunks);
    this.chunks = [];
    const down = downsample(trimSilence(pcm, this.sampleRate), this.sampleRate, TARGET_RATE);
    return { blob: encodeWav(down, TARGET_RATE), durationMs, hadSpeech: this.hadSpeech };
  }

  cancel() {
    if (!this.running) return;
    this.running = false;
    clearTimeout(this.raf);
    try { this.stream.getTracks().forEach((t) => t.stop()); } catch (_) {}
    try { this.ctx.close(); } catch (_) {}
    this.chunks = [];
  }
}

function concat(chunks) {
  const total = chunks.reduce((n, c) => n + c.length, 0);
  const out = new Float32Array(total);
  let offset = 0;
  for (const c of chunks) {
    out.set(c, offset);
    offset += c.length;
  }
  return out;
}

// Drop long trailing silence (keeps 250 ms) so uploads stay small
function trimSilence(pcm, rate) {
  const win = Math.floor(rate * 0.02);
  let end = pcm.length;
  while (end > win) {
    let peak = 0;
    for (let i = end - win; i < end; i++) peak = Math.max(peak, Math.abs(pcm[i]));
    if (peak > 0.02) break;
    end -= win;
  }
  return pcm.subarray(0, Math.min(pcm.length, end + Math.floor(rate * 0.25)));
}

function downsample(pcm, from, to) {
  if (from === to) return pcm;
  const ratio = from / to;
  const out = new Float32Array(Math.floor(pcm.length / ratio));
  for (let i = 0; i < out.length; i++) {
    // box filter over the source window: cheap anti-aliasing
    const start = Math.floor(i * ratio);
    const end = Math.min(pcm.length, Math.floor((i + 1) * ratio));
    let sum = 0;
    for (let j = start; j < end; j++) sum += pcm[j];
    out[i] = sum / Math.max(1, end - start);
  }
  return out;
}

function encodeWav(samples, rate) {
  const buffer = new ArrayBuffer(44 + samples.length * 2);
  const view = new DataView(buffer);
  const writeStr = (offset, str) => [...str].forEach((ch, i) => view.setUint8(offset + i, ch.charCodeAt(0)));
  writeStr(0, "RIFF");
  view.setUint32(4, 36 + samples.length * 2, true);
  writeStr(8, "WAVE");
  writeStr(12, "fmt ");
  view.setUint32(16, 16, true);
  view.setUint16(20, 1, true);          // PCM
  view.setUint16(22, 1, true);          // mono
  view.setUint32(24, rate, true);
  view.setUint32(28, rate * 2, true);   // byte rate
  view.setUint16(32, 2, true);          // block align
  view.setUint16(34, 16, true);         // bits per sample
  writeStr(36, "data");
  view.setUint32(40, samples.length * 2, true);
  let offset = 44;
  for (let i = 0; i < samples.length; i++, offset += 2) {
    const s = Math.max(-1, Math.min(1, samples[i]));
    view.setInt16(offset, s < 0 ? s * 0x8000 : s * 0x7fff, true);
  }
  return new Blob([view], { type: "audio/wav" });
}
