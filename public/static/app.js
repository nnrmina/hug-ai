// HUG — AI Voice Life Assistant for Samsung Galaxy S22+
// Voice/typed commands → FastAPI agent (/api/v1) → confirmation → on-device action

const INITIAL_CONTACTS = [
  {
    id: "sister",
    alias: "bacım",
    aliases: ["bacım", "bacim", "bacı", "baci", "bacıma", "almaz", "almaza"],
    display_name: "Almaz xala (Bacım)",
    short_name: "Almaz xala",
    relation_title: "Bacınız Almaz xalaya",
    phone_number: "+994 50 456 78 90",
    initial: "A"
  },
  {
    id: "daughter",
    alias: "qızım",
    aliases: ["qızım", "qizim", "qızıma", "sevinc", "sevincə"],
    display_name: "Sevinc Məmmədova (Qızım)",
    short_name: "Sevinc",
    relation_title: "Qızınız Sevincə",
    phone_number: "+994 50 123 45 67",
    initial: "S"
  },
  {
    id: "mother",
    alias: "anam",
    aliases: ["anam", "mama", "mamama", "anama", "mamam"],
    display_name: "Anam (Mama)",
    short_name: "Mama",
    relation_title: "Mamanıza",
    phone_number: "+994 55 234 56 78",
    initial: "M"
  },
  {
    id: "son",
    alias: "oğlum",
    aliases: ["oğlum", "oglum", "oğluma", "murad", "murada"],
    display_name: "Murad (Oğlum)",
    short_name: "Murad",
    relation_title: "Oğlunuz Murada",
    phone_number: "+994 70 345 67 89",
    initial: "M"
  },
  {
    id: "doctor",
    alias: "həkim",
    aliases: ["həkim", "hekim", "həkimə", "nigar", "doktor"],
    display_name: "Dr. Nigar Həkim",
    short_name: "Dr. Nigar",
    relation_title: "Dr. Nigar Həkimə",
    phone_number: "+994 50 765 43 21",
    initial: "H"
  }
];

// Pre-rendered neural Azerbaijani clips (az-AZ-BanuNeural) for fixed phrases.
// Everything dynamic is spoken via the backend /api/v1/tts endpoint (speakText).
const AZ_AUDIO_MAP = {
  listen: "/static/audio/listen.mp3",
  call_end: "/static/audio/call_end.mp3",
  order_done: "/static/audio/order_done.mp3",
  action_cancel: "/static/audio/action_cancel.mp3"
};

let recognition = null;
let isListening = false;
let callTimerInterval = null;
let callSeconds = 0;
let currentActionPayload = null;
let currentAudio = null;
let audioUnlocked = false;

// MediaRecorder state for optional OpenAI Whisper
let mediaRecorder = null;
let audioStream = null;
let recordedChunks = [];

// Hands-free confirmation state
let confirmRecognition = null;

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
function findContact(query) {
  if (!query) return null;
  const q = query.toLowerCase();

  for (const c of INITIAL_CONTACTS) {
    for (const a of c.aliases) {
      if (q.includes(a)) {
        return c;
      }
    }
  }
  return null;
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

// ----------------------------------------------------
// Backend API (FastAPI agent at /api/v1)
// ----------------------------------------------------
const API_BASE = "/api/v1";
let currentActionId = null;

async function apiRequest(path, options = {}) {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

// Speak any Azerbaijani sentence with the server's neural voice (az-AZ-BanuNeural),
// falling back to the browser's own speechSynthesis if the server can't synthesize.
function speakText(text, onEnded = null) {
  unlockAudio();
  if (currentAudio) {
    try { currentAudio.pause(); } catch (_) {}
    currentAudio = null;
  }
  if (!text) {
    if (onEnded) onEnded();
    return;
  }

  const audio = new Audio(`${API_BASE}/tts?text=${encodeURIComponent(text.slice(0, 600))}`);
  currentAudio = audio;
  let finished = false;
  const done = () => {
    if (finished) return;
    finished = true;
    if (currentAudio === audio) currentAudio = null;
    if (onEnded) onEnded();
  };
  const fallback = (err) => {
    if (finished || currentAudio !== audio) return;
    console.warn("Neural TTS unavailable, using browser voice:", err);
    finished = true;
    currentAudio = null;
    speakAz(text, onEnded);
  };
  audio.onended = done;
  audio.onerror = fallback;
  const playPromise = audio.play();
  if (playPromise !== undefined) playPromise.catch(fallback);
}

// Word-level yes/no detection (substring checks matched "he" inside "həkim" etc.)
const YES_WORDS = new Set(["bəli", "beli", "hə", "he", "həri", "heri", "oldu", "aha", "yes", "ok", "okay", "təsdiq", "təsdiqlə", "təsdiqləyirəm", "razıyam", "razıyam."]);
const NO_WORDS = new Set(["xeyr", "yox", "ləğv", "legv", "no", "dayan", "saxla"]);

function classifyConfirmation(spoken) {
  const words = spoken.toLowerCase().split(/[\s,.!?;:]+/).filter(Boolean);
  if (words.some((w) => NO_WORDS.has(w)) || spoken.toLowerCase().includes("lazım deyil")) return "no";
  if (words.some((w) => YES_WORDS.has(w))) return "yes";
  return null;
}

// Confirmation Workflow: Only proceeds when the user ACTUALLY says "Bəli" or taps the button.
// Listening starts only after the question has finished playing, so the assistant's own
// "Bəli deyin" can't be picked up by the microphone and auto-confirm the action.
function startConfirmation(questionText) {
  clearConfirmWorkflow();
  showScreen("screen-confirm");

  const voiceLabelEl = document.getElementById("confirm-voice-label");
  if (voiceLabelEl) voiceLabelEl.textContent = "“Bəli” və ya “Xeyr” deyin...";

  speakText(`${questionText} Bəli və ya xeyr deyin.`, () => {
    if (!document.getElementById("screen-confirm").classList.contains("active")) return;
    if (voiceLabelEl) voiceLabelEl.textContent = "🎙️ Eşidirəm... “Bəli” deyin";
    listenForConfirmation(voiceLabelEl);
  });
}

function listenForConfirmation(voiceLabelEl) {
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) return;
  try {
    confirmRecognition = new SpeechRecognition();
    confirmRecognition.lang = "az-AZ";
    confirmRecognition.interimResults = false;
    confirmRecognition.maxAlternatives = 3;

    confirmRecognition.onresult = (event) => {
      const alternatives = Array.from(event.results[0]).map((r) => r.transcript || "");
      const decision = alternatives.map(classifyConfirmation).find(Boolean);
      console.log("Confirmation heard:", alternatives, "→", decision);
      if (decision === "yes") {
        if (voiceLabelEl) voiceLabelEl.textContent = "✓ Səslə təsdiqləndi!";
        executeConfirmedAction();
      } else if (decision === "no") {
        cancelCurrentAction();
      } else if (voiceLabelEl) {
        voiceLabelEl.textContent = "Başa düşmədim. Düyməyə toxunun və ya “Bəli” deyin.";
      }
    };
    confirmRecognition.onerror = () => console.log("Confirmation mic silent");
    confirmRecognition.start();
  } catch (_) {}
}

// Executes the confirmed action: tell the backend first, then run the on-device part.
async function executeConfirmedAction() {
  clearConfirmWorkflow();
  if (!currentActionPayload || !currentActionId) return;
  const payload = currentActionPayload;

  let result;
  try {
    result = await apiRequest(`/assistant/confirm/${currentActionId}`, { method: "POST" });
  } catch (err) {
    showReply({ title: "Xəta baş verdi", text: `Əməliyyat təsdiqlənmədi: ${err.message}`, icon: "!", tone: "muted" });
    return;
  }
  currentActionId = null;

  if (payload.type === "CALL") {
    startCall(payload.contact);
  } else if (payload.type === "ORDER_FOOD" || payload.type === "ORDER_PHARMACY") {
    startOrderTracking(payload.order, result.response);
  } else if (payload.type === "ORDER_TAXI") {
    startTaxiTracking(result.response);
  } else if (payload.type === "CREATE_REMINDER") {
    await openReminders(result.response);
  } else {
    document.getElementById("done-message-subtext").textContent = result.response;
    showScreen("screen-done");
    speakText(result.response);
  }
}

async function cancelCurrentAction() {
  clearConfirmWorkflow();
  const actionId = currentActionId;
  currentActionId = null;
  currentActionPayload = null;
  showScreen("screen-home");
  playAzAudio("action_cancel", "Əməliyyat ləğv edildi.");
  if (actionId) {
    apiRequest(`/assistant/cancel/${actionId}`, { method: "POST" }).catch(() => {});
  }
}

// Generic answer screen (greetings, scam analysis, clarification, rejections)
function showReply({ title, text, heard = "", icon = "✦", tone = "" }) {
  clearConfirmWorkflow();
  document.getElementById("reply-title").textContent = title;
  document.getElementById("reply-text").textContent = text;
  document.getElementById("reply-heard").textContent = heard ? `Siz: “${heard}”` : "";
  const iconEl = document.getElementById("reply-icon");
  iconEl.textContent = icon;
  iconEl.className = `reply-icon${tone ? " " + tone : ""}`;
  showScreen("screen-reply");
  speakText(text);
}

function fillConfirmScreen({ badge, title, primary, secondary, yesLabel }) {
  document.getElementById("confirm-avatar-badge").textContent = badge;
  document.getElementById("confirm-question-title").textContent = title;
  document.getElementById("confirm-details-primary").textContent = primary;
  document.getElementById("confirm-details-secondary").textContent = secondary;
  document.getElementById("btn-confirm-yes").textContent = yesLabel;
}

// Backend may return Baku wall-clock time without an offset (SQLite); treat it as +04:00
function parseBakuTime(iso) {
  if (!iso) return new Date(NaN);
  const hasZone = /[zZ]|[+-]\d{2}:?\d{2}$/.test(iso);
  return new Date(hasZone ? iso : `${iso}+04:00`);
}

const AZ_MONTHS = ["yanvar", "fevral", "mart", "aprel", "may", "iyun", "iyul", "avqust", "sentyabr", "oktyabr", "noyabr", "dekabr"];

// Formatted by hand: many browsers ship without Azerbaijani locale data ("M11 10")
function formatReminderTime(iso) {
  const d = parseBakuTime(iso);
  if (Number.isNaN(d.getTime())) return iso || "";
  const baku = new Date(d.getTime() + 4 * 3600 * 1000); // read UTC fields as Baku (+04:00, no DST)
  const hh = String(baku.getUTCHours()).padStart(2, "0");
  const mm = String(baku.getUTCMinutes()).padStart(2, "0");
  return `${baku.getUTCDate()} ${AZ_MONTHS[baku.getUTCMonth()]} · ${hh}:${mm}`;
}

// Process recognized speech or typed text through the backend agent
async function handleProcessedVoice(text) {
  if (!text || !text.trim()) {
    showMicError("Heç bir səs eşidilmədi. Zəhmət olmasa təkrar danışın.");
    return;
  }
  text = text.trim();

  const quoteEl = document.getElementById("recognized-speech-quote");
  if (quoteEl) quoteEl.textContent = `“${text}”`;
  const badgeEl = document.getElementById("listening-status-badge");
  if (badgeEl) badgeEl.textContent = "⏳ Düşünürəm...";

  let data;
  try {
    data = await apiRequest("/assistant/message", {
      method: "POST",
      body: JSON.stringify({ message: text })
    });
  } catch (err) {
    console.error("Assistant request failed:", err);
    showMicError("Serverlə əlaqə qurulmadı. Bir az sonra təkrar cəhd edin.");
    return;
  }

  if (badgeEl) badgeEl.textContent = "✓ Eşidildi";
  routeAssistantResponse(data, text);
}

function routeAssistantResponse(data, heardText) {
  const intent = data.intent;
  const action = data.action_data || {};
  currentActionId = data.action_id || null;
  currentActionPayload = null;

  if (data.status === "needs_confirmation") {
    // ---- Calls: contact is resolved ON THE DEVICE from the alias (contacts never leave the phone)
    if (intent === "MAKE_CALL" || intent === "SEND_VOICE_MESSAGE") {
      const candidates = [action.contact_alias, ...(action.search_candidates || [])].filter(Boolean);
      const contact = candidates.map(findContact).find(Boolean);
      if (!contact) {
        const alias = action.contact_alias || "bu şəxs";
        if (currentActionId) {
          apiRequest(`/assistant/cancel/${currentActionId}`, { method: "POST" }).catch(() => {});
        }
        currentActionId = null;
        showReply({
          title: "Kontakt tapılmadı",
          text: `“${alias}” adlı kontakt telefonunuzda tapılmadı. Adı bir daha deyin.`,
          heard: heardText,
          icon: "?",
          tone: "muted"
        });
        return;
      }

      const isCall = intent === "MAKE_CALL";
      currentActionPayload = { type: isCall ? "CALL" : "VOICE_MESSAGE", contact };
      fillConfirmScreen({
        badge: contact.initial,
        title: isCall ? `${contact.relation_title} zəng edilsin?` : `${contact.relation_title} səsli mesaj göndərilsin?`,
        primary: contact.display_name,
        secondary: `Mobil · ${contact.phone_number}`,
        yesLabel: isCall ? "Bəli, zəng et" : "Bəli, göndər"
      });
      startConfirmation(isCall ? `${contact.relation_title} zəng edilsin?` : `${contact.relation_title} səsli mesaj göndərilsin?`);
      return;
    }

    // ---- Reminders
    if (intent === "CREATE_REMINDER") {
      currentActionPayload = { type: "CREATE_REMINDER" };
      fillConfirmScreen({
        badge: "⏰",
        title: "Xatırlatma yaradılsın?",
        primary: action.title || "Xatırlatma",
        secondary: formatReminderTime(action.scheduled_at),
        yesLabel: "Bəli, yarat"
      });
      startConfirmation(data.response);
      return;
    }

    // ---- Simulated Wolt orders
    if (intent === "ORDER_FOOD" || intent === "ORDER_PHARMACY" || intent === "ORDER_TAXI") {
      const order = action.order || {};
      currentActionPayload = { type: intent, order };
      const isTaxi = intent === "ORDER_TAXI";
      fillConfirmScreen({
        badge: order.emoji || "🛍️",
        title: isTaxi ? "Taksi çağırılsın?" : `${order.vendor} sifarişi təsdiqlənsin?`,
        primary: order.item || "",
        secondary: `Cəmi ${order.price || ""} · ${order.vendor || "Wolt"} (demo)`,
        yesLabel: isTaxi ? "Bəli, taksi çağır" : "Bəli, sifariş et"
      });
      startConfirmation(data.response);
      return;
    }

    // ---- Anything else that needs confirmation
    currentActionPayload = { type: "GENERAL" };
    fillConfirmScreen({
      badge: "✦",
      title: "Əməliyyat icra edilsin?",
      primary: `“${heardText}”`,
      secondary: data.response,
      yesLabel: "Bəli, icra et"
    });
    startConfirmation(data.response);
    return;
  }

  // ---- No confirmation needed: just answer
  currentActionId = null;
  if (intent === "ANALYZE_MESSAGE") {
    const risk = action.risk_level || "low";
    showReply({
      title: risk === "high" ? "Diqqət: fırıldaq riski!" : risk === "medium" ? "Ehtiyatlı olun" : "Təhlükə görünmür",
      text: data.response,
      icon: risk === "low" ? "✓" : "!",
      tone: risk === "high" ? "risk-high" : risk === "medium" ? "risk-medium" : ""
    });
    return;
  }
  if (data.status === "rejected") {
    showReply({ title: "Bunu edə bilmərəm", text: data.response, heard: heardText, icon: "✕", tone: "muted" });
    return;
  }
  if (data.status === "needs_clarification") {
    showReply({ title: "Başa düşmədim", text: data.response, heard: heardText, icon: "?", tone: "muted" });
    return;
  }
  showReply({ title: "HUG", text: data.response, heard: heardText });
}

// Reminders screen backed by GET /api/v1/reminders
async function openReminders(spokenText = "Xatırlatmalarınız ekrandadır.") {
  clearConfirmWorkflow();
  showScreen("screen-reminders");
  const listEl = document.getElementById("reminders-list");
  if (listEl) listEl.innerHTML = '<p class="reminders-empty">Yüklənir...</p>';
  speakText(spokenText);

  let reminders = [];
  try {
    reminders = await apiRequest("/reminders");
  } catch (err) {
    if (listEl) listEl.innerHTML = '<p class="reminders-empty">Xatırlatmalar yüklənmədi.</p>';
    return;
  }
  if (!listEl) return;

  const upcoming = reminders
    .filter((r) => r.status === "pending")
    .sort((a, b) => new Date(a.scheduled_at) - new Date(b.scheduled_at));
  if (upcoming.length === 0) {
    listEl.innerHTML = '<p class="reminders-empty">Hələ xatırlatma yoxdur. Məsələn deyin: “Sabah saat 10-da dərmanımı xatırlat”.</p>';
    return;
  }

  listEl.innerHTML = "";
  for (const r of upcoming) {
    const card = document.createElement("div");
    card.className = "reminder-item-card samsung-card";
    const info = document.createElement("div");
    const h4 = document.createElement("h4");
    h4.textContent = r.title;
    const p = document.createElement("p");
    p.textContent = formatReminderTime(r.scheduled_at);
    info.append(h4, p);
    const badge = document.createElement("span");
    badge.className = "time-badge";
    badge.textContent = relativeTimeAz(r.scheduled_at);
    card.append(info, badge);
    listEl.append(card);
  }
}

function relativeTimeAz(iso) {
  const target = parseBakuTime(iso);
  const diffMin = Math.round((target - new Date()) / 60000);
  if (Number.isNaN(diffMin)) return "";
  if (diffMin < 0) return "keçib";
  if (diffMin < 60) return `${diffMin} dəq sonra`;
  const hours = Math.round(diffMin / 60);
  if (hours < 24) return `${hours} saat sonra`;
  return `${Math.round(hours / 24)} gün sonra`;
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

  // Play Native Azerbaijani Voice: "Eşidirəm, buyurun"
  playAzAudio("listen", "Eşidirəm, buyurun");

  // If a quick pill was tapped explicitly, use that text
  if (samplePrompt) {
    setTimeout(() => {
      handleProcessedVoice(samplePrompt);
    }, 1100);
    return;
  }

  // Check if OpenAI Whisper is configured
  const openAiKey = localStorage.getItem("hug_openai_api_key");
  const voiceEngine = localStorage.getItem("hug_voice_engine") || "browser";

  if (voiceEngine === "openai" && openAiKey) {
    // OpenAI Whisper Real Audio Recording
    startWhisperRecording(openAiKey);
    return;
  }

  // Native Browser SpeechRecognition (Default & Free)
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    showMicError("Mikrofon bu brauzerdə dəstəklənmir. Zəhmət olmasa Chrome və ya Samsung Internet istifadə edin.");
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
      console.log("Speech recognition error:", event.error);
      if (!hasHeardSpeech) {
        if (event.error === "not-allowed") {
          showMicError("Mikrofona icazə verilmədi. Brauzer parametrlərində mikrofona icazə verin.");
        } else {
          showMicError("Səs eşidilmədi. Zəhmət olmasa danışın və ya düyməyə basaraq təkrar cəhd edin.");
        }
      }
    };

    recognition.onend = () => {
      if (!hasHeardSpeech && document.getElementById("screen-listening").classList.contains("active")) {
        showMicError("Danışıq başa çatdı. Zəhmət olmasa təkrar cəhd edin.");
      }
    };

    recognition.start();
  } catch (err) {
    console.warn("Recognition start error:", err);
    showMicError("Mikrofon işə düşmədi. Zəhmət olmasa səhifəni yeniləyin.");
  }
}

// OpenAI Whisper Real Audio Recording Handler
async function startWhisperRecording(apiKey) {
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

      try {
        const formData = new FormData();
        formData.append("file", audioBlob, "audio.webm");
        formData.append("model", "whisper-1");
        formData.append("language", "az");

        const res = await fetch("https://api.openai.com/v1/audio/transcriptions", {
          method: "POST",
          headers: { Authorization: `Bearer ${apiKey}` },
          body: formData
        });

        if (!res.ok) {
          const errData = await res.json().catch(() => ({}));
          showMicError(`Whisper xətası: ${errData.error?.message || "API açarı yoxlayın"}`);
          return;
        }

        const data = await res.json();
        if (data.text && data.text.trim()) {
          handleProcessedVoice(data.text);
        } else {
          showMicError("Heç bir səs tanınmadı. Zəhmət olmasa təkrar danışın.");
        }
      } catch (err) {
        showMicError("OpenAI ilə əlaqə qurulmadı. İnternet bağlantınızı yoxlayın.");
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

  const rawPhone = contact.phone_number.replace(/\s+/g, "");
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

  speakText(`${contact.short_name} ilə əlaqə qurulur.`);

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

// Wolt Order Tracking Workflow (simulated – order details come from the backend)
function startOrderTracking(order = {}, spokenText = "") {
  showScreen("screen-order-tracking");

  const setText = (id, value) => {
    const el = document.getElementById(id);
    if (el && value) el.textContent = value;
  };
  setText("order-food-emoji", order.emoji);
  setText("order-card-title", order.item);
  setText("order-card-subtitle", order.vendor ? `${order.vendor} (Wolt)` : "");
  setText("order-card-price", order.price);
  setText("order-card-breakdown", order.breakdown);

  const woltBtn = document.getElementById("btn-wolt-deep-link");
  if (woltBtn && order.deep_link) woltBtn.href = order.deep_link;

  speakText(spokenText || "Sifarişiniz qəbul olundu. Kuryer yoldadır.");
}

// Wolt Taxi Tracking Workflow (simulated)
function startTaxiTracking(spokenText = "") {
  showScreen("screen-taxi-tracking");
  speakText(spokenText || "Taksi təsdiqləndi.");
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

  // 1b. Typed command (same backend path as voice)
  const textForm = document.getElementById("text-command-form");
  const textInput = document.getElementById("text-command-input");
  if (textForm && textInput) {
    textForm.addEventListener("submit", (e) => {
      e.preventDefault();
      const value = textInput.value.trim();
      if (!value) return;
      textInput.value = "";
      clearConfirmWorkflow();
      unlockAudio();
      showScreen("screen-listening");
      const retryBtn = document.getElementById("btn-retry-listening");
      const finishBtn = document.getElementById("btn-finish-recording");
      if (retryBtn) retryBtn.style.display = "none";
      if (finishBtn) finishBtn.style.display = "none";
      handleProcessedVoice(value);
    });
  }

  const btnReplyTalk = document.getElementById("btn-reply-talk");
  if (btnReplyTalk) {
    btnReplyTalk.addEventListener("click", () => startListeningWorkflow());
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

  // 3. Quick Scenario Pill Buttons
  document.querySelectorAll(".quick-pill-btn").forEach((pill) => {
    pill.addEventListener("click", (e) => {
      const scenario = e.currentTarget.getAttribute("data-scenario");
      if (scenario === "call-sister") {
        startListeningWorkflow("Bacıma yığ");
      } else if (scenario === "call-daughter") {
        startListeningWorkflow("Qızıma zəng et");
      } else if (scenario === "order-chef-tantuni") {
        startListeningWorkflow("Chef Tantunidən yemək sifariş edirəm");
      } else if (scenario === "order-pharmacy") {
        startListeningWorkflow("Aptekdən kardiomaqnil sifariş et");
      } else if (scenario === "order-taxi") {
        startListeningWorkflow("Taksi çağır");
      }
    });
  });

  // 4. Navigation / Back Buttons
  document.querySelectorAll(".btn-go-home").forEach((btn) => {
    btn.addEventListener("click", () => {
      clearConfirmWorkflow();
      stopCurrentRecording();
      if (currentActionId) {
        apiRequest(`/assistant/cancel/${currentActionId}`, { method: "POST" }).catch(() => {});
        currentActionId = null;
      }
      clearInterval(callTimerInterval);
      showScreen("screen-home");
    });
  });

  // 5. Reminders Avatar Button
  const btnReminders = document.getElementById("btn-open-reminders");
  if (btnReminders) {
    btnReminders.addEventListener("click", () => {
      openReminders();
    });
  }

  // 6. Contacts Icon Button
  const btnContacts = document.getElementById("btn-open-contacts");
  if (btnContacts) {
    btnContacts.addEventListener("click", () => {
      startListeningWorkflow("Bacıma yığ");
    });
  }

  // 7. Settings Modal
  const btnSettings = document.getElementById("btn-open-settings");
  const modalSettings = document.getElementById("settings-modal");
  const btnCloseSettings = document.getElementById("btn-close-settings");
  const engineBrowserBtn = document.getElementById("engine-btn-browser");
  const engineOpenAIBtn = document.getElementById("engine-btn-openai");
  const openAIKeyContainer = document.getElementById("openai-key-container");
  const openAIKeyInput = document.getElementById("openai-api-key");
  const btnSaveSettings = document.getElementById("btn-save-settings");

  if (btnSettings && modalSettings) {
    btnSettings.addEventListener("click", () => {
      const savedEngine = localStorage.getItem("hug_voice_engine") || "browser";
      const savedKey = localStorage.getItem("hug_openai_api_key") || "";

      if (savedEngine === "openai") {
        engineOpenAIBtn.classList.add("active");
        engineBrowserBtn.classList.remove("active");
        openAIKeyContainer.classList.remove("hidden");
      } else {
        engineBrowserBtn.classList.add("active");
        engineOpenAIBtn.classList.remove("active");
        openAIKeyContainer.classList.add("hidden");
      }

      if (openAIKeyInput) openAIKeyInput.value = savedKey;
      modalSettings.classList.remove("hidden");
    });
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
      const isWhisper = engineOpenAIBtn.classList.contains("active");
      localStorage.setItem("hug_voice_engine", isWhisper ? "openai" : "browser");
      if (openAIKeyInput) {
        localStorage.setItem("hug_openai_api_key", openAIKeyInput.value.trim());
      }
      modalSettings.classList.add("hidden");
      alert(isWhisper ? "OpenAI Whisper aktivləşdirildi!" : "Daxili Brauzer Səs Tanıması aktivdir.");
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
      cancelCurrentAction();
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
