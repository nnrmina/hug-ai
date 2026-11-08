// HUG — AI Voice Life Assistant for Samsung Galaxy S22+
// Real Microphone Recording, Natural Azerbaijani Voice & Zero Fake Auto-Executions

const INITIAL_CONTACTS = [
  {
    id: "grandmother",
    alias: "nənəm",
    aliases: ["nənəm", "nenem", "nənə", "nene", "nənəmə", "neneme", "nənəyə", "neneye", "nənəmin", "nenemin"],
    display_name: "Nənəm (Fatma nənə)",
    short_name: "Nənəm",
    relation_title: "Nənənizə",
    phone_number: "+994 50 987 65 43",
    initial: "N",
    audio_confirm: "call_nene_confirm",
    audio_active: "call_nene_active"
  },
  {
    id: "sister",
    alias: "bacım",
    aliases: ["bacım", "bacim", "bacı", "baci", "bacıma", "bacima", "almaz", "almaza"],
    display_name: "Almaz xala (Bacım)",
    short_name: "Almaz xala",
    relation_title: "Bacınız Almaz xalaya",
    phone_number: "+994 50 456 78 90",
    initial: "A",
    audio_confirm: "call_sister_confirm",
    audio_active: "call_sister_active"
  },
  {
    id: "daughter",
    alias: "qızım",
    aliases: ["qızım", "qizim", "qız", "qiz", "qızıma", "qizima", "sevinc", "sevincə", "sevince"],
    display_name: "Sevinc Məmmədova (Qızım)",
    short_name: "Sevinc",
    relation_title: "Qızınız Sevincə",
    phone_number: "+994 50 123 45 67",
    initial: "S",
    audio_confirm: "call_daughter_confirm",
    audio_active: "call_daughter_active"
  },
  {
    id: "mother",
    alias: "anam",
    aliases: ["anam", "mama", "mamama", "anama", "mamam", "ana", "anaya", "mamaya"],
    display_name: "Anam (Mama)",
    short_name: "Mama",
    relation_title: "Mamanıza",
    phone_number: "+994 55 234 56 78",
    initial: "M",
    audio_confirm: "call_mother_confirm",
    audio_active: "call_mother_active"
  },
  {
    id: "son",
    alias: "oğlum",
    aliases: ["oğlum", "oglum", "oğul", "ogul", "oğluma", "ogluma", "murad", "murada"],
    display_name: "Murad (Oğlum)",
    short_name: "Murad",
    relation_title: "Oğlunuz Murada",
    phone_number: "+994 70 345 67 89",
    initial: "M",
    audio_confirm: "call_mother_confirm",
    audio_active: "call_mother_active"
  },
  {
    id: "doctor",
    alias: "həkim",
    aliases: ["həkim", "hekim", "həkimə", "hekime", "nigar", "doktor"],
    display_name: "Dr. Nigar Həkim",
    short_name: "Dr. Nigar",
    relation_title: "Dr. Nigar Həkimə",
    phone_number: "+994 50 765 43 21",
    initial: "H",
    audio_confirm: "call_doctor_confirm",
    audio_active: "call_sister_active"
  }
];

// Pre-rendered Studio Neural Azerbaijani Voice Files (az-AZ-BanuNeural)
const AZ_AUDIO_MAP = {
  listen: "/static/audio/listen.mp3",
  call_sister_confirm: "/static/audio/call_sister_confirm.mp3",
  call_daughter_confirm: "/static/audio/call_daughter_confirm.mp3",
  call_mother_confirm: "/static/audio/call_mother_confirm.mp3",
  call_doctor_confirm: "/static/audio/call_doctor_confirm.mp3",
  call_sister_active: "/static/audio/call_sister_active.mp3",
  call_daughter_active: "/static/audio/call_daughter_active.mp3",
  call_mother_active: "/static/audio/call_mother_active.mp3",
  call_end: "/static/audio/call_end.mp3",
  chef_tantuni_confirm: "/static/audio/chef_tantuni_confirm.mp3",
  chef_tantuni_active: "/static/audio/chef_tantuni_active.mp3",
  pharmacy_confirm: "/static/audio/pharmacy_confirm.mp3",
  pharmacy_active: "/static/audio/pharmacy_active.mp3",
  taxi_confirm: "/static/audio/taxi_confirm.mp3",
  taxi_active: "/static/audio/taxi_active.mp3",
  reminders: "/static/audio/reminders.mp3",
  order_done: "/static/audio/order_done.mp3",
  action_cancel: "/static/audio/action_cancel.mp3",
  call_nene_confirm: "/static/audio/call_nene_confirm.mp3",
  call_nene_active: "/static/audio/call_nene_active.mp3",
  not_understood: "/static/audio/not_understood.mp3"
};

let recognition = null;
let isListening = false;
let callTimerInterval = null;
let callSeconds = 0;
let currentActionPayload = null;
let currentAudio = null;
let audioUnlocked = false;

// MediaRecorder state for optional server-side Whisper
let mediaRecorder = null;
let audioStream = null;
let recordedChunks = [];

// Hands-free confirmation state
let confirmRecognition = null;
let currentCancelHandler = null;

// ----------------------------------------------------
// Backend API helpers
// ----------------------------------------------------
const API_BASE = "/api/v1";
let sessionUserId = null;

function safeStorageGet(key) {
  try { return localStorage.getItem(key); } catch (_) { return null; }
}
function safeStorageSet(key, value) {
  try { localStorage.setItem(key, value); } catch (_) {}
}
function safeStorageRemove(key) {
  try { localStorage.removeItem(key); } catch (_) {}
}

function newUuid() {
  if (window.crypto && typeof window.crypto.randomUUID === "function") {
    return window.crypto.randomUUID();
  }
  const bytes = new Uint8Array(16);
  window.crypto.getRandomValues(bytes);
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (b) => b.toString(16).padStart(2, "0")).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}

// Random per-device identity; it is what keeps one user's reminders separate from another's.
function getUserId() {
  let id = safeStorageGet("hug_user_id");
  if (!id) {
    id = sessionUserId || newUuid();
    sessionUserId = id;
    safeStorageSet("hug_user_id", id);
  }
  return id;
}

// ----------------------------------------------------
// Device authentication: the server issues a signed token; it never trusts a user_id we send.
// The old per-device UUID is sent once as legacy_user_id so existing reminders stay with this device.
// ----------------------------------------------------
let authTokenPromise = null;

function getStoredToken() {
  const token = safeStorageGet("hug_auth_token");
  const expires = Date.parse(safeStorageGet("hug_auth_expires") || "");
  if (token && (!expires || expires - Date.now() > 60000)) return token;
  return null;
}

async function fetchJson(path, options) {
  try {
    const res = await fetch(`${API_BASE}${path}`, options);
    let data = null;
    try { data = await res.json(); } catch (_) {}
    return { ok: res.ok, status: res.status, data };
  } catch (_) {
    return { ok: false, status: 0, data: null };
  }
}

function ensureAuthToken(forceRefresh = false) {
  if (!forceRefresh) {
    const stored = getStoredToken();
    if (stored) return Promise.resolve(stored);
  }
  if (!authTokenPromise) {
    authTokenPromise = (async () => {
      const savedUser = safeStorageGet("hug_auth_user");
      const savedSecret = safeStorageGet("hug_device_secret");
      // Known device: get a new token for the SAME account (data is kept).
      // First run: register; the old pre-login UUID is offered once so its reminders are kept.
      const payload = savedUser && savedSecret
        ? { user_id: savedUser, device_secret: savedSecret }
        : { legacy_user_id: getUserId() };
      const result = await fetchJson("/auth/device", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      authTokenPromise = null;
      if (!result.ok || !result.data || !result.data.access_token) return null;
      safeStorageSet("hug_auth_token", result.data.access_token);
      safeStorageSet("hug_auth_expires", result.data.expires_at || "");
      safeStorageSet("hug_auth_user", result.data.user_id);
      if (result.data.device_secret) safeStorageSet("hug_device_secret", result.data.device_secret);
      return result.data.access_token;
    })();
  }
  return authTokenPromise;
}

async function apiRequest(method, path, body = null, isForm = false, isRetry = false) {
  const token = await ensureAuthToken(isRetry);
  if (!token) {
    return { ok: false, status: 401, data: { detail: "Serverə giriş alınmadı. Səhifəni yeniləyin." } };
  }
  const options = { method, headers: { Authorization: `Bearer ${token}` } };
  if (body !== null) {
    if (isForm) {
      options.body = body;
    } else {
      options.headers["Content-Type"] = "application/json";
      options.body = JSON.stringify(body);
    }
  }
  const result = await fetchJson(path, options);
  // Expired/invalid token: register again once and retry the request once.
  if (result.status === 401 && !isRetry) {
    safeStorageRemove("hug_auth_token");
    return apiRequest(method, path, body, isForm, true);
  }
  return result;
}

function apiErrorText(result, fallback) {
  if (result.status === 0) return "Serverlə əlaqə yoxdur. İnternet bağlantınızı yoxlayın.";
  const detail = result.data && result.data.detail;
  if (typeof detail === "string") return detail;
  return fallback;
}

// ----------------------------------------------------
// Azerbaijani text helpers
// ----------------------------------------------------
function azLower(text) {
  return (text || "").replace(/I/g, "ı").replace(/İ/g, "i").toLowerCase();
}

function tokenize(text) {
  return azLower(text).split(/[^\p{L}\p{N}]+/u).filter(Boolean);
}

function hasWord(text, words) {
  const tokens = tokenize(text);
  return words.some((w) => tokens.includes(w));
}

function hasAnyPrefix(text, prefixes) {
  const tokens = tokenize(text);
  return prefixes.some((p) => tokens.some((t) => t.startsWith(p)));
}

// Decide whether a spoken confirmation is yes / no / unclear.
// Negatives are checked FIRST and only whole words count, so "Yox, zəng etmə" or "heç lazım deyil"
// can never be read as "yes". Anything unclear returns null and the app keeps waiting.
function classifyYesNo(spoken) {
  const lower = azLower(spoken);
  const tokens = tokenize(spoken);
  const negativeWords = ["xeyr", "yox", "yoxdur", "ləğv", "istəmirəm", "lazım", "dayan", "saxla", "heç", "no", "nə", "etmə", "eləmə", "vurma", "yığma"];
  if (tokens.some((t) => negativeWords.includes(t)) || lower.includes("lazım deyil") || lower.includes("ləğv et")) {
    return "no";
  }
  const positiveWords = ["bəli", "beli", "hə", "he", "həri", "heri", "hı", "oldu", "olar", "təsdiq", "təsdiqləyirəm", "razıyam", "əlbəttə", "aha", "yes", "ok", "okey"];
  if (tokens.some((t) => positiveWords.includes(t))) {
    return "yes";
  }
  return null;
}

// ----------------------------------------------------
// Contacts: phone numbers are entered by the user and kept only on this device
// ----------------------------------------------------
function loadContactPhones() {
  try {
    return JSON.parse(safeStorageGet("hug_contact_phones") || "{}") || {};
  } catch (_) {
    return {};
  }
}

function normalizeAzPhone(raw) {
  const digits = (raw || "").replace(/[^\d+]/g, "");
  const only = digits.replace(/\D/g, "");
  if (/^994\d{9}$/.test(only)) return `+${only}`;
  if (/^0\d{9}$/.test(only)) return `+994${only.slice(1)}`;
  if (/^\d{9}$/.test(only)) return `+994${only}`;
  return null;
}

function getContactPhone(contact) {
  const custom = loadContactPhones()[contact.id];
  return custom || contact.phone_number || "+994 50 123 45 67";
}

function formatPhoneForDisplay(phone) {
  const m = /^\+994(\d{2})(\d{3})(\d{2})(\d{2})$/.exec(phone || "");
  return m ? `+994 ${m[1]} ${m[2]} ${m[3]} ${m[4]}` : phone;
}

// Play Chime on Mic Activation
function playChime() {
  try {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (!AudioContext) return;
    const ctx = new AudioContext();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.setValueAtTime(523.25, ctx.currentTime);
    osc.frequency.exponentialRampToValueAtTime(659.25, ctx.currentTime + 0.12);
    gain.gain.setValueAtTime(0.12, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.28);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.3);
  } catch (_) {}
}

// Audio Unlock for Mobile Browsers
function unlockAudio() {
  if (audioUnlocked) return;
  audioUnlocked = true;
  if ("speechSynthesis" in window) {
    if (window.speechSynthesis.paused) {
      window.speechSynthesis.resume();
    }
  }
}
document.addEventListener("click", unlockAudio, { once: true });
document.addEventListener("touchstart", unlockAudio, { once: true });

// Screen Switcher
function showScreen(screenId) {
  const screens = document.querySelectorAll(".screen-view");
  screens.forEach((s) => s.classList.remove("active"));

  const target = document.getElementById(screenId);
  if (target) {
    target.classList.add("active");
  }
}

// Primary Voice Player: Studio Neural Azerbaijani Audio
function playAzAudio(key, fallbackText = null, onEnded = null) {
  unlockAudio();

  if (currentAudio) {
    try {
      currentAudio.pause();
      currentAudio.currentTime = 0;
    } catch (_) {}
    currentAudio = null;
  }

  const audioUrl = AZ_AUDIO_MAP[key];
  if (audioUrl) {
    const audio = new Audio(audioUrl);
    currentAudio = audio;

    if (onEnded) {
      audio.onended = () => {
        currentAudio = null;
        onEnded();
      };
    } else {
      audio.onended = () => {
        currentAudio = null;
      };
    }

    const playPromise = audio.play();
    if (playPromise !== undefined) {
      playPromise.catch((err) => {
        console.warn("Audio play blocked/failed, using fallback:", err);
        if (fallbackText) {
          speakAz(fallbackText, onEnded);
        } else if (onEnded) {
          onEnded();
        }
      });
    }
    return;
  }

  if (fallbackText) {
    speakAz(fallbackText, onEnded);
  } else if (onEnded) {
    onEnded();
  }
}

// Fallback Speech Synthesis with clean Azerbaijani/Turkish phonetics
function speakAz(text, onEndedCallback = null) {
  if (!("speechSynthesis" in window) || !text) {
    if (onEndedCallback) onEndedCallback();
    return;
  }
  try {
    unlockAudio();
    window.speechSynthesis.cancel();

    const voices = window.speechSynthesis.getVoices() || [];
    let azVoice = voices.find(
      (v) => v.lang && (v.lang.toLowerCase().startsWith("az") || v.name.toLowerCase().includes("azerba"))
    );

    if (!azVoice) {
      azVoice = voices.find(
        (v) => v.lang && (v.lang.toLowerCase().startsWith("tr") || v.name.toLowerCase().includes("turk"))
      );
    }

    let spokenText = text;
    if (azVoice && azVoice.lang && azVoice.lang.toLowerCase().startsWith("tr")) {
      spokenText = text.replace(/ə/g, "e").replace(/Ə/g, "E");
    }

    const u = new SpeechSynthesisUtterance(spokenText);
    if (azVoice) {
      u.voice = azVoice;
      u.lang = azVoice.lang;
    } else {
      u.lang = "tr-TR";
    }
    u.rate = 0.90;
    u.pitch = 1.0;
    u.volume = 1.0;

    if (onEndedCallback) {
      u.onend = onEndedCallback;
    }

    window.speechSynthesis.speak(u);
  } catch (err) {
    console.warn("TTS error:", err);
    if (onEndedCallback) onEndedCallback();
  }
}

// Contact Lookup
// Whole-word matching only ("anam" must not match inside "Anamnez", "mama" inside "mamamız").
// Returns null when nothing or more than one contact matches — the app then asks instead of guessing.
function findContact(query) {
  if (!query) return null;
  const tokens = tokenize(query);
  const matches = INITIAL_CONTACTS.filter((c) => c.aliases.some((a) => tokens.includes(azLower(a))));
  return matches.length === 1 ? matches[0] : null;
}

// Clear Confirmation Workflow Timers & Listeners
function clearConfirmWorkflow() {
  if (confirmRecognition) {
    try { confirmRecognition.stop(); } catch (_) {}
    confirmRecognition = null;
  }
  if (currentAudio) {
    try {
      currentAudio.pause();
      currentAudio.currentTime = 0;
    } catch (_) {}
    currentAudio = null;
  }
}

// Confirmation Workflow: Only proceeds when the user ACTUALLY speaks "Bəli" or clicks the button!
function startConfirmation(audioKey, questionVoicePrompt, onConfirmCallback, onCancelCallback = null) {
  clearConfirmWorkflow();
  currentCancelHandler = onCancelCallback;
  showScreen("screen-confirm");

  const voiceLabelEl = document.getElementById("confirm-voice-label");
  if (voiceLabelEl) {
    voiceLabelEl.textContent = "“Bəli” və ya “Xeyr” deyin...";
  }

  // 1. Play Studio-Quality Native Azerbaijani Audio
  playAzAudio(audioKey, questionVoicePrompt, () => {
    if (voiceLabelEl) {
      voiceLabelEl.textContent = "🎙️ Eşidirəm... “Bəli” deyin";
    }
  });

  // 2. Listen for voice confirmation (Bəli / Xeyr)
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (SpeechRecognition) {
    try {
      confirmRecognition = new SpeechRecognition();
      confirmRecognition.lang = "az-AZ";
      confirmRecognition.interimResults = false;
      confirmRecognition.maxAlternatives = 1;

      confirmRecognition.onresult = (event) => {
        const spoken = event.results[0][0].transcript || "";
        const answer = classifyYesNo(spoken);

        if (answer === "no") {
          cancelCurrentConfirmation();
        } else if (answer === "yes") {
          clearConfirmWorkflow();
          if (voiceLabelEl) voiceLabelEl.textContent = "✓ Səslə təsdiqləndi!";
          currentCancelHandler = null;
          onConfirmCallback();
        } else if (voiceLabelEl) {
          // Unclear answer: never guess. Ask again and wait for a clear "Bəli"/"Xeyr" or a button tap.
          voiceLabelEl.textContent = "Başa düşmədim. “Bəli” və ya “Xeyr” deyin, ya da düyməyə toxunun.";
        }
      };

      confirmRecognition.onerror = () => {
        // If voice confirmation is silent, wait for user to click or speak again
        console.log("Confirmation mic silent");
      };

      setTimeout(() => {
        if (confirmRecognition) {
          try { confirmRecognition.start(); } catch (_) {}
        }
      }, 1500);
    } catch (_) {}
  }
}

// Cancel the pending confirmation (voice "Xeyr" or the cancel button)
function cancelCurrentConfirmation() {
  clearConfirmWorkflow();
  const handler = currentCancelHandler;
  currentCancelHandler = null;
  if (handler) {
    try { handler(); } catch (_) {}
  }
  currentActionPayload = null;
  showScreen("screen-home");
  playAzAudio("action_cancel", "Əməliyyat ləğv edildi.");
}

// Executes the confirmed action
async function executeConfirmedAction() {
  clearConfirmWorkflow();
  currentCancelHandler = null;
  const payload = currentActionPayload;
  if (!payload) return;

  if (payload.type === "CALL") {
    startCall(payload.contact);
  } else if (
    payload.type === "ORDER" ||
    payload.type === "ORDER_FOOD" ||
    payload.type === "ORDER_PHARMACY"
  ) {
    startOrderTracking();
  } else if (payload.type === "ORDER_TAXI") {
    startTaxiTracking();
  } else if (payload.type === "BACKEND_ACTION") {
    const result = await apiRequest("POST", `/assistant/confirm/${encodeURIComponent(payload.actionId)}`);
    if (!result.ok) {
      showInfoMessage(apiErrorText(result, "Əməliyyat təsdiqlənmədi."), true);
      return;
    }
    const data = result.data || {};
    const actionData = data.action_data || {};
    if (payload.intent === "EMERGENCY_CALL" && actionData.authorized_execution === "OPEN_DIALER") {
      const number = actionData.phone_number || "103";
      speakAz(data.response || `${number} yığılır.`);
      window.location.href = `tel:${number}`;
      showInfoMessage(data.response || `${number} yığılır.`);
      return;
    }
    if (payload.intent === "CREATE_REMINDER") {
      speakAz(data.response || "Xatırlatma yaradıldı.");
      openRemindersScreen();
      return;
    }
    document.getElementById("done-message-subtext").textContent = data.response || "Əməliyyat təsdiqləndi.";
    showScreen("screen-done");
  }
  currentActionPayload = null;
}

// Shows a spoken + written message on the listening screen with a retry button
function showInfoMessage(message, isError = false) {
  showScreen("screen-listening");
  const quoteEl = document.getElementById("recognized-speech-quote");
  const badgeEl = document.getElementById("listening-status-badge");
  const retryBtn = document.getElementById("btn-retry-listening");
  const finishBtn = document.getElementById("btn-finish-recording");
  if (quoteEl) quoteEl.textContent = message;
  if (badgeEl) badgeEl.textContent = isError ? "⚠️ Diqqət" : "ℹ️ Cavab";
  if (retryBtn) retryBtn.style.display = "block";
  if (finishBtn) finishBtn.style.display = "none";
  speakAz(message);
}

function showConfirmScreen({ badge, title, primary, secondary, yesLabel }) {
  document.getElementById("confirm-avatar-badge").textContent = badge;
  document.getElementById("confirm-question-title").textContent = title;
  document.getElementById("confirm-details-primary").textContent = primary;
  document.getElementById("confirm-details-secondary").textContent = secondary;
  document.getElementById("btn-confirm-yes").textContent = yesLabel;
}

// ----------------------------------------------------
// Intent detection helpers (whole words, Azerbaijani-aware)
// ----------------------------------------------------
function isCallCommand(text) {
  return hasWord(text, ["zəng", "zeng", "zvanok", "yığ", "yig"]) || /nömrəsini\s+yığ|əlaqə\s+saxla/u.test(azLower(text));
}

function isReminderCommand(text) {
  const lower = azLower(text);
  return hasAnyPrefix(text, ["xatırla", "xatirla"]) || lower.includes("yadıma sal") || lower.includes("yadima sal") ||
    hasWord(text, ["oyat"]) || lower.includes("zəngli saat");
}

function hasOrderVerb(text) {
  return hasAnyPrefix(text, ["sifariş", "sifaris", "gətir", "getir", "al", "istəyirəm"]);
}

// Demo-only order scenarios (nothing is really ordered). Medicines are only matched when the user
// explicitly asks to order/buy, so "dərmanımı xatırlat" is a reminder, never a pharmacy order.
function detectDemoOrder(text) {
  if (hasAnyPrefix(text, ["chef", "tantuni", "bozbaş", "bozbas", "dönər", "doner"]) || (hasAnyPrefix(text, ["yemək", "yemek"]) && hasOrderVerb(text))) {
    return "ORDER_FOOD";
  }
  if (hasAnyPrefix(text, ["aptek"]) || (hasAnyPrefix(text, ["dərman", "derman", "kardiomaqnil"]) && hasOrderVerb(text))) {
    return "ORDER_PHARMACY";
  }
  if (hasAnyPrefix(text, ["taksi", "taxi"])) {
    return "ORDER_TAXI";
  }
  return null;
}

function extractDynamicContact(text) {
  const lower = azLower(text);
  let cleaned = lower
    .replace(/\b(zəng\s*et|zeng\s*et|zəng\s*elə|zeng\s*ele|zəng\s*vur|yığ|yig|zvanok|telefon|aç|zəng|zeng|elə|ele|et|edərsiniz|edin|zəhmət\s*olmasa|mənə|mənim|üçün|nömrəsini|xahiş\s*edirəm)\b/gu, "")
    .trim();

  if (cleaned.endsWith("mə") || cleaned.endsWith("ma")) {
    cleaned = cleaned.slice(0, -2);
  } else if (cleaned.endsWith("yə") || cleaned.endsWith("ya")) {
    cleaned = cleaned.slice(0, -2);
  } else if (cleaned.endsWith("ə") || cleaned.endsWith("a")) {
    cleaned = cleaned.slice(0, -1);
  }
  cleaned = cleaned.trim();

  if (cleaned.length >= 2) {
    const capitalized = cleaned.charAt(0).toUpperCase() + cleaned.slice(1);
    return {
      id: "custom_" + cleaned,
      alias: cleaned,
      aliases: [cleaned, lower],
      display_name: capitalized,
      short_name: capitalized,
      relation_title: `${capitalized} şəxsinə`,
      phone_number: "+994 50 123 45 67",
      initial: capitalized.charAt(0),
      audio_confirm: null,
      audio_active: null
    };
  }
  return null;
}

function startCallConfirmation(contact) {
  const phone = getContactPhone(contact);
  currentActionPayload = { type: "CALL", contact };
  showConfirmScreen({
    badge: contact.initial,
    title: `${contact.relation_title} zəng edilsin?`,
    primary: contact.display_name,
    secondary: `Mobil · ${formatPhoneForDisplay(phone)}`,
    yesLabel: "Bəli, zəng et",
  });
  startConfirmation(contact.audio_confirm, `${contact.relation_title} zəng edilsin? Bəli və ya xeyr deyin.`, executeConfirmedAction);
}

function startDemoOrder(kind, text) {
  if (kind === "ORDER_FOOD") {
    const isTantuni = hasAnyPrefix(text, ["tantuni", "chef"]);
    currentActionPayload = {
      type: "ORDER_FOOD",
      vendor: isTantuni ? "Chef Tantuni" : "Wolt Restoran",
      item: isTantuni ? "Tantuni · 1 pors" : "Bozbaş · Orta pors",
      price: isTantuni ? "8.50 AZN" : "12.00 AZN",
      breakdown: isTantuni ? "Yemək 6.50 AZN + Wolt Çatdırılma 2.00 AZN" : "Yemək 10.00 AZN + Wolt Çatdırılma 2.00 AZN",
      emoji: isTantuni ? "🌯" : "🍲",
      deepLink: isTantuni
        ? "https://wolt.com/az/aze/baku/search?q=chef+tantuni"
        : "https://wolt.com/az/aze/baku/search?q=bozbas"
    };
    showConfirmScreen({
      badge: currentActionPayload.emoji,
      title: `${currentActionPayload.vendor} sifarişi göstərilsin? (Demo)`,
      primary: currentActionPayload.item,
      secondary: `Təxmini ${currentActionPayload.price} · DEMO — real sifariş verilmir`,
      yesLabel: "Bəli, göstər",
    });
    startConfirmation(isTantuni ? "chef_tantuni_confirm" : null,
      `${currentActionPayload.vendor} sifarişi göstərilsin? Bu demo rejimdir. Bəli və ya xeyr deyin.`, executeConfirmedAction);
  } else if (kind === "ORDER_PHARMACY") {
    currentActionPayload = {
      type: "ORDER_PHARMACY",
      vendor: "Aptek (Wolt)",
      item: "Dərmanınızı Wolt-da axtarın",
      price: "",
      breakdown: "Dərmanı həkiminizin təyin etdiyi kimi seçin.",
      emoji: "💊",
      deepLink: "https://wolt.com/az/aze/baku/search?q=aptek"
    };
    showConfirmScreen({
      badge: "💊",
      title: "Aptek axtarışı açılsın? (Demo)",
      primary: "Wolt-da aptek axtarışı",
      secondary: "DEMO — dərman avtomatik seçilmir və sifariş verilmir",
      yesLabel: "Bəli, aç",
    });
    startConfirmation(null, "Woltda aptek axtarışı açılsın? Dərman avtomatik seçilmir. Bəli və ya xeyr deyin.", executeConfirmedAction);
  } else if (kind === "ORDER_TAXI") {
    currentActionPayload = { type: "ORDER_TAXI" };
    showConfirmScreen({
      badge: "🚕",
      title: "Taksi nümunəsi göstərilsin? (Demo)",
      primary: "Taksi çağırışı nümunəsi",
      secondary: "DEMO — real taksi çağırılmır",
      yesLabel: "Bəli, göstər",
    });
    startConfirmation(null, "Taksi nümunəsi göstərilsin? Real taksi çağırılmır. Bəli və ya xeyr deyin.", executeConfirmedAction);
  }
}

// Sends the command to the backend agent and handles reminders, emergencies, security checks and questions.
async function handleWithBackend(text) {
  const result = await apiRequest("POST", "/assistant/message", { message: text });
  if (!result.ok || !result.data) {
    showInfoMessage("Bağışlayın, tam başa düşmədim. Zəhmət olmasa təkrar edin.", true);
    playAzAudio("not_understood", "Bağışlayın, tam başa düşmədim. Zəhmət olmasa təkrar edin.");
    return;
  }
  const data = result.data;
  const actionData = data.action_data || {};

  if (data.status === "needs_confirmation" && data.action_id) {
    const cancelBackend = () => apiRequest("POST", `/assistant/cancel/${encodeURIComponent(data.action_id)}`);

    if (data.intent === "MAKE_CALL" || data.intent === "SEND_VOICE_MESSAGE") {
      cancelBackend();
      let contact = findContact(`${actionData.contact_alias || ""} ${text}`);
      if (!contact) {
        contact = extractDynamicContact(`${actionData.contact_alias || ""} ${text}`);
      }
      if (!contact) {
        showInfoMessage("Kimə zəng etmək istədiyinizi tapa bilmədim. Məsələn: “Nənəmə zəng et” deyin.", true);
        return;
      }
      startCallConfirmation(contact);
      return;
    }

    currentActionPayload = { type: "BACKEND_ACTION", actionId: data.action_id, intent: data.intent };
    if (data.intent === "EMERGENCY_CALL") {
      showConfirmScreen({
        badge: "🚑",
        title: `${actionData.phone_number || "103"} nömrəsinə zəng edilsin?`,
        primary: "Təcili yardım",
        secondary: data.response,
        yesLabel: "Bəli, zəng et",
      });
    } else if (data.intent === "CREATE_REMINDER") {
      showConfirmScreen({
        badge: "⏰",
        title: "Xatırlatma yaradılsın?",
        primary: actionData.title || "Xatırlatma",
        secondary: data.response,
        yesLabel: "Bəli, yarat",
      });
    } else {
      showConfirmScreen({ badge: "✦", title: "Təsdiqləyirsiniz?", primary: text, secondary: data.response, yesLabel: "Bəli" });
    }
    startConfirmation(null, `${data.response} Bəli və ya xeyr deyin.`, executeConfirmedAction, cancelBackend);
    return;
  }

  // completed (security analysis, questions), rejected, needs_clarification -> just tell the user
  showInfoMessage(data.response || "Bağışlayın, tam başa düşmədim. Məsələn: “Nənəmə zəng et” və ya “Taksi çağır” deyin.", data.status === "rejected");
  if (!data.response) {
    playAzAudio("not_understood", "Bağışlayın, tam başa düşmədim. Zəhmət olmasa təkrar edin.");
  }
}

// Process Real Spoken Voice Text
async function handleProcessedVoice(text) {
  if (!text || !text.trim()) {
    showMicError("Heç bir səs eşidilmədi. Zəhmət olmasa təkrar danışın.");
    return;
  }

  const quoteEl = document.getElementById("recognized-speech-quote");
  if (quoteEl) {
    quoteEl.textContent = `“${text}”`;
  }

  const badgeEl = document.getElementById("listening-status-badge");
  if (badgeEl) {
    badgeEl.textContent = "✓ Eşidildi";
  }

  // 1. Reminders before everything else, so "dərmanımı xatırlat" or "zəngli saat" is never a call/order.
  if (isReminderCommand(text)) {
    await handleWithBackend(text);
    return;
  }

  // 2. Direct calls to contacts or spoken names (resolved on-device, zero privacy leak)
  if (isCallCommand(text) && !/\b(103|112)\b/u.test(text)) {
    let contact = findContact(text);
    if (!contact) {
      contact = extractDynamicContact(text);
    }
    if (contact) {
      startCallConfirmation(contact);
      return;
    }
  }

  // Also check if user just spoke a contact's name directly (e.g. "Nənəm", "Fatma nənə", "Mama", "Sevinc")
  const directContact = findContact(text);
  if (directContact) {
    startCallConfirmation(directContact);
    return;
  }

  // 3. Demo order scenarios (clearly labelled, nothing real is ordered)
  const demoKind = detectDemoOrder(text);
  if (demoKind) {
    startDemoOrder(demoKind, text);
    return;
  }

  // 4. Everything else (emergencies, unknown names, scam checks, questions) goes to the backend agent
  await handleWithBackend(text);
}

// ----------------------------------------------------
// Reminders screen (real data from the backend)
// ----------------------------------------------------
const AZ_MONTHS = ["Yanvar", "Fevral", "Mart", "Aprel", "May", "İyun", "İyul", "Avqust", "Sentyabr", "Oktyabr", "Noyabr", "Dekabr"];

function formatReminderTime(date) {
  const now = new Date();
  const startOfDay = (d) => new Date(d.getFullYear(), d.getMonth(), d.getDate()).getTime();
  const dayDiff = Math.round((startOfDay(date) - startOfDay(now)) / 86400000);
  const time = date.toLocaleTimeString("az-AZ", { hour: "2-digit", minute: "2-digit", timeZone: "Asia/Baku" });
  const label = dayDiff === 0 ? "Bu gün" : dayDiff === 1 ? "Sabah" : `${date.getDate()} ${AZ_MONTHS[date.getMonth()].toLowerCase()}`;
  return `${label} · ${time}`;
}

function renderCalendar(reminders) {
  const grid = document.getElementById("calendar-grid");
  const title = document.getElementById("cal-month-title");
  if (!grid) return;
  const now = new Date();
  const year = now.getFullYear();
  const month = now.getMonth();
  if (title) title.textContent = `${AZ_MONTHS[month]} ${year}`;

  const eventDays = new Set(
    reminders
      .map((r) => new Date(r.scheduled_at))
      .filter((d) => d.getFullYear() === year && d.getMonth() === month)
      .map((d) => d.getDate())
  );

  grid.replaceChildren();
  const firstWeekday = (new Date(year, month, 1).getDay() + 6) % 7; // Monday = 0
  for (let i = 0; i < firstWeekday; i++) {
    const blank = document.createElement("span");
    blank.className = "cal-day dim";
    grid.appendChild(blank);
  }
  const daysInMonth = new Date(year, month + 1, 0).getDate();
  for (let day = 1; day <= daysInMonth; day++) {
    const cell = document.createElement("span");
    cell.className = "cal-day";
    if (day === now.getDate()) cell.classList.add("today");
    if (eventDays.has(day)) cell.classList.add("active-event");
    cell.textContent = String(day);
    grid.appendChild(cell);
  }
}

async function loadReminders() {
  const list = document.getElementById("reminders-list");
  if (!list) return;
  const result = await apiRequest("GET", "/reminders");
  list.replaceChildren();

  if (!result.ok || !Array.isArray(result.data)) {
    const p = document.createElement("p");
    p.className = "reminder-empty";
    p.textContent = apiErrorText(result, "Xatırlatmaları yükləmək mümkün olmadı.");
    list.appendChild(p);
    renderCalendar([]);
    return;
  }

  const upcoming = result.data.filter((r) => r.status === "pending");
  renderCalendar(upcoming);

  if (upcoming.length === 0) {
    const p = document.createElement("p");
    p.className = "reminder-empty";
    p.textContent = "Hələ xatırlatma yoxdur. “Sabah saat 9-da dərmanımı xatırlat” deyin.";
    list.appendChild(p);
    return;
  }

  upcoming.forEach((r) => {
    const card = document.createElement("div");
    card.className = "reminder-item-card samsung-card";
    const info = document.createElement("div");
    const h4 = document.createElement("h4");
    h4.textContent = r.title;
    const p = document.createElement("p");
    p.textContent = formatReminderTime(new Date(r.scheduled_at));
    info.append(h4, p);

    const del = document.createElement("button");
    del.className = "reminder-delete-btn";
    del.type = "button";
    del.textContent = "Sil";
    del.setAttribute("aria-label", `${r.title} xatırlatmasını sil`);
    del.addEventListener("click", async () => {
      if (!window.confirm(`“${r.title}” xatırlatması silinsin?`)) return;
      const res = await apiRequest("DELETE", `/reminders/${encodeURIComponent(r.id)}`);
      if (!res.ok) alert(apiErrorText(res, "Silmək mümkün olmadı."));
      loadReminders();
    });

    const actions = document.createElement("div");
    actions.className = "reminder-actions";
    actions.appendChild(del);
    card.append(info, actions);
    list.appendChild(card);
  });
}

function openRemindersScreen() {
  clearConfirmWorkflow();
  showScreen("screen-reminders");
  loadReminders();
}

// Show clear message when microphone was silent (NO FAKE AUTO EXECUTION)
function showMicError(message) {
  const quoteEl = document.getElementById("recognized-speech-quote");
  const badgeEl = document.getElementById("listening-status-badge");
  const retryBtn = document.getElementById("btn-retry-listening");
  const finishBtn = document.getElementById("btn-finish-recording");

  if (quoteEl) quoteEl.textContent = message;
  if (badgeEl) badgeEl.textContent = "⚠️ Səs aşkar olunmadı";
  if (retryBtn) retryBtn.style.display = "block";
  if (finishBtn) finishBtn.style.display = "none";
}

// Real Voice Recording Engine
async function startListeningWorkflow(samplePrompt = null) {
  clearConfirmWorkflow();
  unlockAudio();
  playChime();
  showScreen("screen-listening");

  const quoteEl = document.getElementById("recognized-speech-quote");
  const badgeEl = document.getElementById("listening-status-badge");
  const retryBtn = document.getElementById("btn-retry-listening");
  const finishBtn = document.getElementById("btn-finish-recording");

  if (quoteEl) quoteEl.textContent = "Danışın, sizi eşidirəm...";
  if (badgeEl) badgeEl.textContent = "🔴 Sizi dinləyirəm...";
  if (retryBtn) retryBtn.style.display = "none";
  if (finishBtn) finishBtn.style.display = "block";

  // If a quick pill was tapped explicitly, use that text
  if (samplePrompt) {
    playAzAudio("listen", "Eşidirəm, buyurun");
    setTimeout(() => {
      handleProcessedVoice(samplePrompt);
    }, 1100);
    return;
  }

  // Play "Eşidirəm, buyurun" FIRST and open the microphone only after it finishes,
  // otherwise the recognizer hears the prompt itself or times out before the user speaks.
  let micStarted = false;
  const startMic = () => {
    if (micStarted || !document.getElementById("screen-listening").classList.contains("active")) return;
    micStarted = true;
    if (badgeEl) badgeEl.textContent = "🔴 Sizi dinləyirəm... danışın";
    startMicrophoneRecognition();
  };
  playAzAudio("listen", "Eşidirəm, buyurun", startMic);
  setTimeout(startMic, 2500); // safety net if the audio "ended" event never fires
}

const SPEECH_ERROR_MESSAGES = {
  "no-speech": "Səs eşidilmədi. Mikrofona yaxın və bir qədər ucadan danışın.",
  "audio-capture": "Mikrofon tapılmadı. Mikrofonun qoşulu olduğunu və başqa proqramın istifadə etmədiyini yoxlayın.",
  "not-allowed": "Mikrofona icazə verilmədi. Ünvan sətrindəki 🔒 işarəsinə basıb mikrofona icazə verin.",
  "service-not-allowed": "Bu brauzer səs tanımaya icazə vermir. Google Chrome istifadə edin.",
  "network": "Səs tanıma xidmətinə qoşulmaq olmadı. Bu brauzer (məs. Edge/Opera/Brave) dəstəkləməyə bilər — Google Chrome istifadə edin və ya Tənzimləmələrdə “Server Whisper” seçin.",
  "language-not-supported": "Bu brauzer Azərbaycan dilində səs tanımanı dəstəkləmir. Google Chrome istifadə edin.",
};

function startMicrophoneRecognition() {
  // Server-side Whisper (the OpenAI key lives only on the server)
  const voiceEngine = safeStorageGet("hug_voice_engine") || "browser";
  if (voiceEngine === "openai") {
    startWhisperRecording();
    return;
  }

  // Native Browser SpeechRecognition (Default & Free)
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    showMicError("Mikrofon bu brauzerdə dəstəklənmir. Zəhmət olmasa Google Chrome və ya Samsung Internet istifadə edin.");
    return;
  }

  try {
    if (recognition) {
      try { recognition.stop(); } catch (_) {}
    }
    recognition = new SpeechRecognition();
    recognition.lang = "az-AZ";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    let hasHeardSpeech = false;
    let lastError = null;

    recognition.onresult = (event) => {
      hasHeardSpeech = true;
      const speechText = event.results[0][0].transcript;
      if (speechText && speechText.trim()) {
        handleProcessedVoice(speechText);
      } else {
        showMicError("Səs aydın eşidilmədi. Zəhmət olmasa bir qədər ucadan təkrar edin.");
      }
    };

    recognition.onerror = (event) => {
      console.warn("Speech recognition error:", event.error);
      lastError = event.error;
      if (!hasHeardSpeech && event.error !== "aborted") {
        showMicError(SPEECH_ERROR_MESSAGES[event.error] || `Səs tanıma xətası: ${event.error}. Yenidən cəhd edin.`);
      }
    };

    recognition.onend = () => {
      // Do not overwrite the specific error message shown by onerror.
      if (!hasHeardSpeech && !lastError && document.getElementById("screen-listening").classList.contains("active")) {
        showMicError("Heç nə eşidilmədi. “Yenidən Danış” düyməsinə basıb siqnaldan sonra danışın.");
      }
    };

    recognition.start();
  } catch (err) {
    console.warn("Recognition start error:", err);
    showMicError("Mikrofon işə düşmədi. Zəhmət olmasa səhifəni yeniləyin.");
  }
}

// Server Whisper Recording Handler: audio is sent to OUR backend, which calls OpenAI with its own key
async function startWhisperRecording() {
  try {
    recordedChunks = [];
    audioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    mediaRecorder = new MediaRecorder(audioStream);

    mediaRecorder.ondataavailable = (e) => {
      if (e.data.size > 0) recordedChunks.push(e.data);
    };

    mediaRecorder.onstop = async () => {
      if (audioStream) {
        audioStream.getTracks().forEach((track) => track.stop());
      }

      if (recordedChunks.length === 0) {
        showMicError("Səs faylı boşdur. Zəhmət olmasa təkrar danışın.");
        return;
      }

      const audioBlob = new Blob(recordedChunks, { type: "audio/webm" });
      const badgeEl = document.getElementById("listening-status-badge");
      const quoteEl = document.getElementById("recognized-speech-quote");
      if (badgeEl) badgeEl.textContent = "⏳ Whisper emal edir...";
      if (quoteEl) quoteEl.textContent = "Səs qeydiniz tanınır...";

      const formData = new FormData();
      formData.append("audio", audioBlob, "audio.webm");
      const result = await apiRequest("POST", "/speech/transcribe", formData, true);

      if (!result.ok) {
        showMicError(apiErrorText(result, "Səs tanınmadı. Zəhmət olmasa təkrar danışın."));
        return;
      }
      const text = result.data && result.data.text;
      if (text && text.trim()) {
        handleProcessedVoice(text);
      } else {
        showMicError("Heç bir səs tanınmadı. Zəhmət olmasa təkrar danışın.");
      }
    };

    mediaRecorder.start();
  } catch (err) {
    showMicError("Mikrofona icazə verilmədi. Brauzer parametrlərini yoxlayın.");
  }
}

// Stop current recording
function stopCurrentRecording() {
  if (mediaRecorder && mediaRecorder.state === "recording") {
    mediaRecorder.stop();
  } else if (recognition) {
    try { recognition.stop(); } catch (_) {}
  }
}

// Active Phone Calling Workflow on Samsung S22+
function startCall(contact) {
  showScreen("screen-calling");
  document.getElementById("calling-contact-name").textContent = contact.short_name || contact.display_name;
  document.getElementById("call-avatar-circle").textContent = contact.initial;

  const rawPhone = getContactPhone(contact);
  if (!rawPhone) {
    showInfoMessage(`${contact.short_name} üçün nömrə yoxdur. Tənzimləmələrdə əlavə edin.`, true);
    return;
  }
  document.getElementById("native-dialer-btn").href = `tel:${rawPhone}`;

  callSeconds = 0;
  clearInterval(callTimerInterval);
  const timerEl = document.getElementById("calling-status-timer");

  callTimerInterval = setInterval(() => {
    callSeconds++;
    const mins = String(Math.floor(callSeconds / 60)).padStart(2, "0");
    const secs = String(callSeconds % 60).padStart(2, "0");
    timerEl.textContent = `Zəng edilir... · ${mins}:${secs}`;
  }, 1000);

  playAzAudio(contact.audio_active, `${contact.short_name} ilə əlaqə qurulur`);

  // Direct trigger to native Samsung Phone dialer
  try {
    window.location.href = `tel:${rawPhone}`;
  } catch (_) {}
}

function endCall() {
  clearInterval(callTimerInterval);
  document.getElementById("done-message-subtext").textContent = "Zənginiz uğurla başa çatdı.";
  showScreen("screen-done");
  playAzAudio("call_end", "Zəng başa çatdı.");
}

// Wolt Order Tracking Workflow
function startOrderTracking() {
  showScreen("screen-order-tracking");

  if (currentActionPayload && currentActionPayload.item) {
    const emojiEl = document.getElementById("order-food-emoji");
    if (emojiEl && currentActionPayload.emoji) {
      emojiEl.textContent = currentActionPayload.emoji;
    }

    const titleEl = document.getElementById("order-card-title");
    if (titleEl) titleEl.textContent = currentActionPayload.item;

    const subEl = document.getElementById("order-card-subtitle");
    if (subEl) subEl.textContent = `${currentActionPayload.vendor} (Wolt)`;

    const priceEl = document.getElementById("order-card-price");
    if (priceEl) priceEl.textContent = currentActionPayload.price;

    const breakEl = document.getElementById("order-card-breakdown");
    if (breakEl) breakEl.textContent = currentActionPayload.breakdown;

    const woltBtn = document.getElementById("btn-wolt-deep-link");
    if (woltBtn && currentActionPayload.deepLink) {
      woltBtn.href = currentActionPayload.deepLink;
    }
  }

  // Honest wording: this is a demo screen, nothing has been ordered.
  speakAz("Bu demo ekrandır, real sifariş verilməyib. Sifariş etmək üçün Wolt düyməsinə toxunun.");
}

// Wolt Taxi Tracking Workflow
function startTaxiTracking() {
  showScreen("screen-taxi-tracking");
  speakAz("Bu demo ekrandır, real taksi çağırılmayıb.");
}

// Initialize Application DOM Events
document.addEventListener("DOMContentLoaded", () => {
  const clockEl = document.getElementById("status-clock");
  if (clockEl) {
    const updateTime = () => {
      const now = new Date();
      clockEl.textContent = now.toLocaleTimeString("az-AZ", { hour: "2-digit", minute: "2-digit" });
    };
    updateTime();
    setInterval(updateTime, 30000);
  }

  // 1. Orb & "Danışmaq üçün toxunun"
  const orbBtn = document.getElementById("ai-orb-btn");
  const tapToTalkBtn = document.getElementById("btn-tap-to-talk");

  if (orbBtn) {
    orbBtn.addEventListener("click", () => startListeningWorkflow());
  }
  if (tapToTalkBtn) {
    tapToTalkBtn.addEventListener("click", () => startListeningWorkflow());
  }

  // 2. Listening Screen Actions
  const btnFinishRec = document.getElementById("btn-finish-recording");
  if (btnFinishRec) {
    btnFinishRec.addEventListener("click", () => {
      stopCurrentRecording();
    });
  }

  const btnRetryRec = document.getElementById("btn-retry-listening");
  if (btnRetryRec) {
    btnRetryRec.addEventListener("click", () => {
      startListeningWorkflow();
    });
  }

  // A browser-stored OpenAI key from older versions is a leak risk — remove it.
  safeStorageRemove("hug_openai_api_key");

  // 4. Navigation / Back Buttons
  document.querySelectorAll(".btn-go-home").forEach((btn) => {
    btn.addEventListener("click", () => {
      clearConfirmWorkflow();
      stopCurrentRecording();
      clearInterval(callTimerInterval);
      showScreen("screen-home");
    });
  });

  // 5. Reminders Avatar Button
  const btnReminders = document.getElementById("btn-open-reminders");
  if (btnReminders) {
    btnReminders.addEventListener("click", () => {
      openRemindersScreen();
      playAzAudio("reminders", "Xatırlatmalarınız ekrandadır.");
    });
  }

  // 7. Settings Modal
  const btnSettings = document.getElementById("btn-open-settings");
  const modalSettings = document.getElementById("settings-modal");
  const btnCloseSettings = document.getElementById("btn-close-settings");
  const engineBrowserBtn = document.getElementById("engine-btn-browser");
  const engineOpenAIBtn = document.getElementById("engine-btn-openai");
  const openAIKeyContainer = document.getElementById("openai-key-container");
  const btnSaveSettings = document.getElementById("btn-save-settings");
  const contactsEditor = document.getElementById("contacts-editor");

  function renderContactsEditor() {
    if (!contactsEditor) return;
    const phones = loadContactPhones();
    contactsEditor.replaceChildren();
    INITIAL_CONTACTS.forEach((c) => {
      const row = document.createElement("div");
      row.className = "contact-row";
      const label = document.createElement("label");
      label.htmlFor = `contact-phone-${c.id}`;
      label.textContent = c.display_name;
      const input = document.createElement("input");
      input.type = "tel";
      input.id = `contact-phone-${c.id}`;
      input.dataset.contactId = c.id;
      input.placeholder = "+994 50 000 00 00";
      input.autocomplete = "off";
      input.value = phones[c.id] ? formatPhoneForDisplay(phones[c.id]) : "";
      row.append(label, input);
      contactsEditor.appendChild(row);
    });
  }

  function openSettings() {
    if (!modalSettings) return;
    const savedEngine = safeStorageGet("hug_voice_engine") || "browser";
    if (savedEngine === "openai") {
      engineOpenAIBtn.classList.add("active");
      engineBrowserBtn.classList.remove("active");
      openAIKeyContainer.classList.remove("hidden");
    } else {
      engineBrowserBtn.classList.add("active");
      engineOpenAIBtn.classList.remove("active");
      openAIKeyContainer.classList.add("hidden");
    }
    renderContactsEditor();
    modalSettings.classList.remove("hidden");
  }

  // 6. Contacts Icon Button opens the contact number editor
  const btnContacts = document.getElementById("btn-open-contacts");
  if (btnContacts) {
    btnContacts.addEventListener("click", openSettings);
  }

  if (btnSettings && modalSettings) {
    btnSettings.addEventListener("click", openSettings);
  }

  if (btnCloseSettings && modalSettings) {
    btnCloseSettings.addEventListener("click", () => {
      modalSettings.classList.add("hidden");
    });
  }

  if (engineBrowserBtn && engineOpenAIBtn) {
    engineBrowserBtn.addEventListener("click", () => {
      engineBrowserBtn.classList.add("active");
      engineOpenAIBtn.classList.remove("active");
      openAIKeyContainer.classList.add("hidden");
    });

    engineOpenAIBtn.addEventListener("click", () => {
      engineOpenAIBtn.classList.add("active");
      engineBrowserBtn.classList.remove("active");
      openAIKeyContainer.classList.remove("hidden");
    });
  }

  if (btnSaveSettings && modalSettings) {
    btnSaveSettings.addEventListener("click", () => {
      // Validate and save contact numbers (device-local only)
      const phones = {};
      let hasInvalid = false;
      if (contactsEditor) {
        contactsEditor.querySelectorAll("input[data-contact-id]").forEach((input) => {
          const raw = input.value.trim();
          if (!raw) {
            input.removeAttribute("aria-invalid");
            return;
          }
          const normalized = normalizeAzPhone(raw);
          if (normalized) {
            phones[input.dataset.contactId] = normalized;
            input.removeAttribute("aria-invalid");
          } else {
            input.setAttribute("aria-invalid", "true");
            hasInvalid = true;
          }
        });
      }
      if (hasInvalid) {
        alert("Bəzi nömrələr yanlışdır. Format: +994 50 123 45 67 və ya 050 123 45 67");
        return;
      }
      safeStorageSet("hug_contact_phones", JSON.stringify(phones));

      const isWhisper = engineOpenAIBtn.classList.contains("active");
      safeStorageSet("hug_voice_engine", isWhisper ? "openai" : "browser");
      modalSettings.classList.add("hidden");
      alert(isWhisper ? "Server Whisper səs tanıması seçildi." : "Brauzerin öz səs tanıması aktivdir.");
    });
  }

  // 8. Confirmation Screen Manual Actions
  const btnConfirmYes = document.getElementById("btn-confirm-yes");
  const btnConfirmCancel = document.getElementById("btn-confirm-cancel");

  if (btnConfirmYes) {
    btnConfirmYes.addEventListener("click", () => {
      executeConfirmedAction();
    });
  }

  if (btnConfirmCancel) {
    btnConfirmCancel.addEventListener("click", () => {
      cancelCurrentConfirmation();
    });
  }

  // 9. Calling Screen Buttons
  const btnEndActiveCall = document.getElementById("btn-end-active-call");
  if (btnEndActiveCall) {
    btnEndActiveCall.addEventListener("click", () => {
      endCall();
    });
  }

  // 10. Order Tracking Finish Button
  const btnOrderFinish = document.getElementById("btn-order-finish");
  if (btnOrderFinish) {
    btnOrderFinish.addEventListener("click", () => {
      document.getElementById("done-message-subtext").textContent = "Sifarişiniz təslim edildi. Nuş olsun!";
      showScreen("screen-done");
      playAzAudio("order_done", "Sifarişiniz tamamlandı. Nuş olsun!");
    });
  }

  // 11. Taxi Cancel Button
  const btnCancelTaxi = document.getElementById("btn-cancel-taxi");
  if (btnCancelTaxi) {
    btnCancelTaxi.addEventListener("click", () => {
      showScreen("screen-home");
      playAzAudio("action_cancel", "Taksi sifarişi ləğv edildi.");
    });
  }
});
