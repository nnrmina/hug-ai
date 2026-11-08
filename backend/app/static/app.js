// HUG — Smooth Screen Transitions, Voice Processing & Azerbaijani Natural Dialog

const INITIAL_CONTACTS = [
  { alias: "mama", display_name: "Anam (Mama)", phone_number: "+994 55 234 56 78" },
  { alias: "anam", display_name: "Anam (Mama)", phone_number: "+994 55 234 56 78" },
  { alias: "qızım", display_name: "Sevinc (Qızım)", phone_number: "+994 50 123 45 67" },
  { alias: "qizim", display_name: "Sevinc (Qızım)", phone_number: "+994 50 123 45 67" },
  { alias: "sevinc", display_name: "Sevinc Məmmədova", phone_number: "+994 50 123 45 67" },
  { alias: "almaz", display_name: "Almaz Məmmədova", phone_number: "+994 50 456 78 90" },
  { alias: "oğlum", display_name: "Murad (Oğlum)", phone_number: "+994 70 345 67 89" },
  { alias: "həkim", display_name: "Dr. Nigar Həkim", phone_number: "+994 50 765 43 21" }
];

let recognition = null;
let isListening = false;
let callTimerInterval = null;
let callSeconds = 0;
let currentActionPayload = null;
let azVoice = null;
let audioUnlocked = false;

// Voice Selector: Prioritizes Azerbaijani, falls back to Turkish (identical phonetic structure), then system default
function initVoices() {
  if (!("speechSynthesis" in window)) return;
  const voices = window.speechSynthesis.getVoices();
  if (!voices || voices.length === 0) return;

  // 1. Look for explicit Azerbaijani voice
  let voice = voices.find(
    (v) => v.lang && (v.lang.toLowerCase().startsWith("az") || v.name.toLowerCase().includes("azerba"))
  );

  // 2. Fallback to Turkish voice (phonetically identical pronunciation for Azerbaijani words)
  if (!voice) {
    voice = voices.find(
      (v) => v.lang && (v.lang.toLowerCase().startsWith("tr") || v.name.toLowerCase().includes("turk"))
    );
  }

  // 3. Fallback to first available voice
  if (!voice) {
    voice = voices.find((v) => v.default) || voices[0];
  }

  azVoice = voice;
}

if ("speechSynthesis" in window) {
  speechSynthesis.onvoiceschanged = initVoices;
  initVoices();
}

// Unlock audio on first user touch/click
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

// Screen Transition Manager
function showScreen(screenId) {
  const screens = document.querySelectorAll(".screen-view");
  screens.forEach((s) => s.classList.remove("active"));

  const target = document.getElementById(screenId);
  if (target) {
    target.classList.add("active");
  }
}

// Natural Azerbaijani Speech Synthesis
function speakAz(text) {
  if (!("speechSynthesis" in window) || !text) return;
  try {
    unlockAudio();
    window.speechSynthesis.cancel();

    initVoices();

    // If using Turkish engine fallback, map 'ə'/'Ə' to 'e'/'E' so phonetics sound 100% natural and clear
    let spokenText = text;
    if (azVoice && azVoice.lang && azVoice.lang.toLowerCase().startsWith("tr")) {
      spokenText = text.replace(/ə/g, "e").replace(/Ə/g, "E");
    }

    const u = new SpeechSynthesisUtterance(spokenText);
    if (azVoice) {
      u.voice = azVoice;
      u.lang = azVoice.lang;
    } else {
      u.lang = "tr-TR"; // Use tr-TR as standard fallback so Chrome doesn't remain silent
    }
    u.rate = 0.92;
    u.pitch = 1.0;
    u.volume = 1.0;

    window.speechSynthesis.speak(u);
  } catch (err) {
    console.warn("TTS error:", err);
  }
}

// Normalizes target name for contacts
function normalizeAzTargetName(raw) {
  if (!raw) return "";
  let s = raw.trim().toLowerCase();
  s = s.replace(/^(salam\s+)?(hug|yaxın|köməkçi)[\s,!]*/i, "");
  s = s.replace(/\s*(üçün\s+)?(zəng\s*et|zeng\s*et|zəng\s*elə|zeng\s*ele|zəng\s*vur|zeng\s*vur|zvanok|telefon\s*aç|yığ|yig).*$/i, "");
  s = s.trim();

  if (s === "mamama" || s === "mamaya" || s === "mama") return "mama";
  if (s === "anama" || s === "anaya" || s === "ana") return "anam";
  if (s === "qızıma" || s === "qizima") return "qızım";
  if (s === "oğluma" || s === "ogluma") return "oğlum";
  if (s === "həkimə" || s === "hekime") return "həkim";
  if (s === "almaza") return "almaz";
  if (s === "sevincə" || s === "sevince") return "sevinc";

  if (s.length > 4 && (s.endsWith("ya") || s.endsWith("yə"))) return s.slice(0, -2);
  if (s.length > 3 && (s.endsWith("a") || s.endsWith("ə"))) return s.slice(0, -1);
  return s;
}

function findContact(query) {
  const norm = normalizeAzTargetName(query);
  const raw = (query || "").trim().toLowerCase();

  for (const c of INITIAL_CONTACTS) {
    const a = c.alias.toLowerCase();
    const n = c.display_name.toLowerCase();
    if (a === raw || a === norm || n.includes(norm) || a.includes(norm) || norm.includes(a)) {
      return c;
    }
  }
  return null;
}

// Processing User Voice Intent
function handleProcessedVoice(text) {
  const quoteEl = document.getElementById("recognized-speech-quote");
  if (quoteEl) {
    quoteEl.textContent = `“${text}”`;
  }

  const lowered = text.toLowerCase();

  // 1. CALL Intent
  if (lowered.includes("zəng") || lowered.includes("zeng") || lowered.includes("yığ") || lowered.includes("yig") || lowered.includes("zvanok") || lowered.includes("telefon")) {
    const contact = findContact(text) || INITIAL_CONTACTS[2]; // Default to Qızım (Sevinc)

    currentActionPayload = {
      type: "CALL",
      contact: contact
    };

    setTimeout(() => {
      document.getElementById("confirm-avatar-badge").textContent = contact.display_name[0].toUpperCase();
      document.getElementById("confirm-question-title").textContent = `${contact.display_name} şəxsinə zəng edilsin?`;
      document.getElementById("confirm-details-primary").textContent = contact.display_name;
      document.getElementById("confirm-details-secondary").textContent = `Mobil · ${contact.phone_number}`;
      document.getElementById("btn-confirm-yes").textContent = "Bəli, zəng et";

      showScreen("screen-confirm");
      speakAz(`${contact.display_name} üçün zəng təsdiqlənsin?`);
    }, 700);
    return;
  }

  // 2. ORDER Intent (Food / Grocery)
  if (lowered.includes("sifariş") || lowered.includes("sifaris") || lowered.includes("zakaz") || lowered.includes("alma") || lowered.includes("bozbaş") || lowered.includes("dönər") || lowered.includes("corek") || lowered.includes("çörək")) {
    currentActionPayload = {
      type: "ORDER",
      item: lowered.includes("bozbaş") ? "Bozbaş · Orta pors" : (lowered.includes("alma") ? "2 kilo Alma" : "Toyuq Dönəri"),
      price: lowered.includes("bozbaş") ? "12 AZN" : (lowered.includes("alma") ? "7 AZN" : "6 AZN")
    };

    setTimeout(() => {
      document.getElementById("confirm-avatar-badge").textContent = "🍲";
      document.getElementById("confirm-question-title").textContent = "Sifarişiniz təsdiqlənsin?";
      document.getElementById("confirm-details-primary").textContent = currentActionPayload.item;
      document.getElementById("confirm-details-secondary").textContent = `Cəmi · ${currentActionPayload.price} (Wolt Çatdırılma)`;
      document.getElementById("btn-confirm-yes").textContent = "Bəli, sifariş et";

      showScreen("screen-confirm");
      speakAz("Sifarişiniz hazırlansın?");
    }, 700);
    return;
  }

  // 3. REMINDER Intent
  if (lowered.includes("xatırla") || lowered.includes("xatirlat") || lowered.includes("yadıma sal") || lowered.includes("yadima sal") || lowered.includes("təqvim") || lowered.includes("teqvim")) {
    setTimeout(() => {
      showScreen("screen-reminders");
      speakAz("Xatırlatmalarınız ekrandadır.");
    }, 700);
    return;
  }

  // Fallback to Confirmation for General Action
  currentActionPayload = {
    type: "GENERAL",
    text: text
  };

  setTimeout(() => {
    document.getElementById("confirm-avatar-badge").textContent = "✦";
    document.getElementById("confirm-question-title").textContent = "Köməkçi əməliyyatı icra etsin?";
    document.getElementById("confirm-details-primary").textContent = `“${text}”`;
    document.getElementById("confirm-details-secondary").textContent = "AI Life Agent Sistemi";
    document.getElementById("btn-confirm-yes").textContent = "Bəli, icra et";

    showScreen("screen-confirm");
    speakAz("Əməliyyatı icra edim?");
  }, 700);
}

// Start Microphone & Audio Waveform
function startListeningWorkflow(samplePrompt = null) {
  showScreen("screen-listening");
  const quoteEl = document.getElementById("recognized-speech-quote");
  quoteEl.textContent = "Sizi dinləyirəm...";
  speakAz("Eşidirəm, buyurun");

  // If a sample text was provided, simulate natural speech
  if (samplePrompt) {
    setTimeout(() => {
      handleProcessedVoice(samplePrompt);
    }, 1200);
    return;
  }

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    // If browser doesn't support Web Speech API, use prompt
    setTimeout(() => {
      const fallbackText = prompt("Mikrofon brauzer tərəfindən dəstəklənmir. Danışmaq istədiyinizi yazın:", "Qızıma zəng et");
      if (fallbackText) {
        handleProcessedVoice(fallbackText);
      } else {
        showScreen("screen-home");
      }
    }, 600);
    return;
  }

  try {
    if (recognition) {
      recognition.stop();
    }
    recognition = new SpeechRecognition();
    recognition.lang = "az-AZ";
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    recognition.onresult = (event) => {
      const speechText = event.results[0][0].transcript;
      handleProcessedVoice(speechText);
    };

    recognition.onerror = () => {
      // If error or blocked, use sample voice interaction
      setTimeout(() => {
        handleProcessedVoice("Qızıma zəng et");
      }, 1000);
    };

    recognition.start();
  } catch (err) {
    setTimeout(() => {
      handleProcessedVoice("Qızıma zəng et");
    }, 1000);
  }
}

// Start Live Calling Screen
function startCall(contact) {
  showScreen("screen-calling");
  document.getElementById("calling-contact-name").textContent = contact.display_name;
  document.getElementById("call-avatar-circle").textContent = contact.display_name[0].toUpperCase();
  document.getElementById("native-dialer-btn").href = `tel:${contact.phone_number.replace(/\s+/g, "")}`;

  callSeconds = 0;
  clearInterval(callTimerInterval);
  const timerEl = document.getElementById("calling-status-timer");

  callTimerInterval = setInterval(() => {
    callSeconds++;
    const mins = String(Math.floor(callSeconds / 60)).padStart(2, "0");
    const secs = String(callSeconds % 60).padStart(2, "0");
    timerEl.textContent = `Zəng edilir... · ${mins}:${secs}`;
  }, 1000);

  speakAz(`${contact.display_name} ilə əlaqə qurulur`);
}

// End Call Screen
function endCall() {
  clearInterval(callTimerInterval);
  document.getElementById("done-message-subtext").textContent = "Zənginiz uğurla başa çatdı.";
  showScreen("screen-done");
  speakAz("Zəng başa çatdı");
}

// Start Order Tracking Screen
function startOrderTracking() {
  showScreen("screen-order-tracking");
  if (currentActionPayload && currentActionPayload.item) {
    document.getElementById("order-card-title").textContent = currentActionPayload.item;
    document.getElementById("order-card-price").textContent = currentActionPayload.price;
  }
  speakAz("Sifarişiniz qəbul olundu. Kuryer yoldadır.");
}

// Initialize DOM Listeners
document.addEventListener("DOMContentLoaded", () => {
  // Real-time clock in status bar
  const clockEl = document.getElementById("status-clock");
  if (clockEl) {
    const updateTime = () => {
      const now = new Date();
      clockEl.textContent = now.toLocaleTimeString("az-AZ", { hour: "2-digit", minute: "2-digit" });
    };
    updateTime();
    setInterval(updateTime, 30000);
  }

  // 1. Orb & "Danışmaq üçün toxunun" Buttons
  const orbBtn = document.getElementById("ai-orb-btn");
  const tapToTalkBtn = document.getElementById("btn-tap-to-talk");

  if (orbBtn) {
    orbBtn.addEventListener("click", () => startListeningWorkflow());
  }
  if (tapToTalkBtn) {
    tapToTalkBtn.addEventListener("click", () => startListeningWorkflow());
  }

  // 2. Navigation & Back Buttons
  document.querySelectorAll(".btn-go-home").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (recognition) {
        try { recognition.stop(); } catch (_) {}
      }
      clearInterval(callTimerInterval);
      showScreen("screen-home");
    });
  });

  // 3. User Avatar / Reminders Button
  const btnReminders = document.getElementById("btn-open-reminders");
  if (btnReminders) {
    btnReminders.addEventListener("click", () => {
      showScreen("screen-reminders");
    });
  }

  // 4. Contacts Button (shortcut to prompt call)
  const btnContacts = document.getElementById("btn-open-contacts");
  if (btnContacts) {
    btnContacts.addEventListener("click", () => {
      startListeningWorkflow("Qızıma zəng et");
    });
  }

  // 5. Confirmation Screen Buttons
  const btnConfirmYes = document.getElementById("btn-confirm-yes");
  const btnConfirmCancel = document.getElementById("btn-confirm-cancel");

  if (btnConfirmYes) {
    btnConfirmYes.addEventListener("click", () => {
      if (currentActionPayload && currentActionPayload.type === "CALL") {
        startCall(currentActionPayload.contact);
      } else if (currentActionPayload && currentActionPayload.type === "ORDER") {
        startOrderTracking();
      } else {
        document.getElementById("done-message-subtext").textContent = "Əməliyyatınız uğurla yerinə yetirildi.";
        showScreen("screen-done");
      }
    });
  }

  if (btnConfirmCancel) {
    btnConfirmCancel.addEventListener("click", () => {
      showScreen("screen-home");
    });
  }

  // 6. Calling Screen End Call Button
  const btnEndActiveCall = document.getElementById("btn-end-active-call");
  if (btnEndActiveCall) {
    btnEndActiveCall.addEventListener("click", () => {
      endCall();
    });
  }

  // 7. Order Tracking Finish Button
  const btnOrderFinish = document.getElementById("btn-order-finish");
  if (btnOrderFinish) {
    btnOrderFinish.addEventListener("click", () => {
      document.getElementById("done-message-subtext").textContent = "Sifarişiniz təslim edildi. Nuş olsun!";
      showScreen("screen-done");
    });
  }
});
