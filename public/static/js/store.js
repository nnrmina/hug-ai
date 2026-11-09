// Client-side state: settings (per device), conversation session and recent turns.

const SETTINGS_KEY = "hug_settings_v2";
const HISTORY_KEY = "hug_history_v1";
const MAX_TURNS = 6;

const DEFAULT_SETTINGS = {
  engine: "auto",        // auto (Gemini when the server has it) | browser
  theme: "system",       // system | light | dark
  contrast: "normal",    // normal | high
  textSize: "normal",    // normal | large | xl
  alerts: true,          // spoken + notification reminder alerts
  conversation: true     // reopen the mic after every spoken answer (hands-free chat)
};

function safeGet(storage, key) {
  try { return storage.getItem(key); } catch (_) { return null; }
}

function safeSet(storage, key, value) {
  try { storage.setItem(key, value); } catch (_) { /* private mode / blocked storage */ }
}

export function loadSettings() {
  try {
    return { ...DEFAULT_SETTINGS, ...(JSON.parse(safeGet(localStorage, SETTINGS_KEY)) || {}) };
  } catch (_) {
    return { ...DEFAULT_SETTINGS };
  }
}

export const settings = loadSettings();

export function saveSettings(patch) {
  Object.assign(settings, patch);
  safeSet(localStorage, SETTINGS_KEY, JSON.stringify(settings));
  applySettings();
}

// Theme / contrast / text size are data-* attributes on <html>; CSS tokens do the rest.
export function applySettings() {
  const root = document.documentElement;
  if (settings.theme === "system") delete root.dataset.theme;
  else root.dataset.theme = settings.theme;
  root.dataset.contrast = settings.contrast;
  root.dataset.textSize = settings.textSize;

  const dark = settings.theme === "dark" ||
    (settings.theme === "system" && window.matchMedia?.("(prefers-color-scheme: dark)").matches);
  document.querySelector('meta[name="theme-color"]')?.setAttribute("content", dark ? "#101711" : "#EBF3E8");
}

// One conversation per tab; survives reloads of the same tab.
function makeId() {
  return crypto.randomUUID ? crypto.randomUUID() : `s-${Date.now()}-${Math.random().toString(16).slice(2)}`;
}

let sessionId = safeGet(sessionStorage, "hug_session");
if (!sessionId) {
  sessionId = makeId();
  safeSet(sessionStorage, "hug_session", sessionId);
}
export const getSessionId = () => sessionId;

let history = [];
try { history = JSON.parse(safeGet(sessionStorage, HISTORY_KEY)) || []; } catch (_) { history = []; }

export const getHistory = () => history.slice(-MAX_TURNS);

export function recordTurn(userText, data) {
  const pending = data.status === "needs_clarification" && data.intent !== "UNKNOWN"
    ? { intent: data.intent, title: data.action_data?.title || null }
    : null;
  history.push({
    user: (userText || "").slice(0, 500),
    assistant: (data.response || "").slice(0, 1000),
    intent: data.intent,
    status: data.status,
    pending
  });
  history = history.slice(-MAX_TURNS);
  safeSet(sessionStorage, HISTORY_KEY, JSON.stringify(history));
}

// Server capabilities (filled by main.js from /api/v1/assistant/capabilities)
export const capabilities = { engine: "rule_based", audio_understanding: false, neural_tts: true };
