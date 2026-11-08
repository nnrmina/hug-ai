// HUG — AI Voice Life Assistant for Samsung Galaxy S22+
// Real Microphone Recording, Natural Azerbaijani Voice & Zero Fake Auto-Executions

const INITIAL_CONTACTS = [
  {
    id: "sister",
    alias: "bacım",
    aliases: ["bacım", "bacim", "bacı", "baci", "bacıma", "almaz", "almaza"],
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
    aliases: ["qızım", "qizim", "qızıma", "sevinc", "sevincə"],
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
    aliases: ["anam", "mama", "mamama", "anama", "mamam"],
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
    aliases: ["oğlum", "oglum", "oğluma", "murad", "murada"],
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
    aliases: ["həkim", "hekim", "həkimə", "nigar", "doktor"],
    display_name: "Dr. Nigar Həkim",
    short_name: "Dr. Nigar",
    relation_title: "Dr. Nigar Həkimə",
    phone_number: "+994 50 765 43 21",
    initial: "H",
    audio_confirm: "call_doctor_confirm",
    audio_active: "call_mother_active"
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

// Confirmation Workflow: Only proceeds when the user ACTUALLY speaks "Bəli" or clicks the button!
function startConfirmation(audioKey, questionVoicePrompt, onConfirmCallback) {
  clearConfirmWorkflow();
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
        const spoken = (event.results[0][0].transcript || "").toLowerCase();
        console.log("Confirmation heard:", spoken);

        if (
          spoken.includes("bəli") ||
          spoken.includes("beli") ||
          spoken.includes("hə") ||
          spoken.includes("he") ||
          spoken.includes("həri") ||
          spoken.includes("oldu") ||
          spoken.includes("təsdiq") ||
          spoken.includes("zəng") ||
          spoken.includes("sifariş") ||
          spoken.includes("aha") ||
          spoken.includes("yes")
        ) {
          clearConfirmWorkflow();
          if (voiceLabelEl) voiceLabelEl.textContent = "✓ Səslə təsdiqləndi!";
          onConfirmCallback();
        } else if (
          spoken.includes("xeyr") ||
          spoken.includes("yox") ||
          spoken.includes("ləğv") ||
          spoken.includes("lazım deyil") ||
          spoken.includes("saxla") ||
          spoken.includes("no")
        ) {
          clearConfirmWorkflow();
          showScreen("screen-home");
          playAzAudio("action_cancel", "Əməliyyat ləğv edildi.");
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

// Executes the confirmed action
function executeConfirmedAction() {
  clearConfirmWorkflow();
  if (!currentActionPayload) return;

  if (currentActionPayload.type === "CALL") {
    startCall(currentActionPayload.contact);
  } else if (
    currentActionPayload.type === "ORDER" ||
    currentActionPayload.type === "ORDER_FOOD" ||
    currentActionPayload.type === "ORDER_PHARMACY"
  ) {
    startOrderTracking();
  } else if (currentActionPayload.type === "ORDER_TAXI") {
    startTaxiTracking();
  } else {
    document.getElementById("done-message-subtext").textContent = "Əməliyyatınız uğurla yerinə yetirildi.";
    showScreen("screen-done");
  }
}

// Process Real Spoken Voice Text
function handleProcessedVoice(text) {
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

  const lowered = text.toLowerCase();

  // ----------------------------------------------------
  // SCENARIO 1: CALL (Bacı, Qızım, Mama, Həkim)
  // ----------------------------------------------------
  if (
    lowered.includes("zəng") ||
    lowered.includes("zeng") ||
    lowered.includes("yığ") ||
    lowered.includes("yig") ||
    lowered.includes("zvanok") ||
    lowered.includes("telefon") ||
    lowered.includes("bacı") ||
    lowered.includes("baci") ||
    lowered.includes("qızım") ||
    lowered.includes("qizim") ||
    lowered.includes("mama")
  ) {
    let matchedContact = findContact(lowered);
    if (!matchedContact) {
      matchedContact = INITIAL_CONTACTS[1]; // Default to Qızım (Sevinc)
    }

    currentActionPayload = {
      type: "CALL",
      contact: matchedContact
    };

    setTimeout(() => {
      document.getElementById("confirm-avatar-badge").textContent = matchedContact.initial;
      document.getElementById("confirm-question-title").textContent = `${matchedContact.relation_title} zəng edilsin?`;
      document.getElementById("confirm-details-primary").textContent = matchedContact.display_name;
      document.getElementById("confirm-details-secondary").textContent = `Mobil · ${matchedContact.phone_number}`;
      document.getElementById("btn-confirm-yes").textContent = "Bəli, zəng et";

      startConfirmation(
        matchedContact.audio_confirm || "call_sister_confirm",
        `${matchedContact.relation_title} zəng edilsin? Bəli deyin.`,
        executeConfirmedAction
      );
    }, 600);
    return;
  }

  // ----------------------------------------------------
  // SCENARIO 2: WOLT FOOD (Chef Tantuni / Yemek)
  // ----------------------------------------------------
  if (
    lowered.includes("chef") ||
    lowered.includes("tantuni") ||
    lowered.includes("bozbaş") ||
    lowered.includes("yemək") ||
    lowered.includes("yemek") ||
    lowered.includes("dönər") ||
    lowered.includes("doner")
  ) {
    const isTantuni = lowered.includes("tantuni") || lowered.includes("chef");

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

    setTimeout(() => {
      document.getElementById("confirm-avatar-badge").textContent = currentActionPayload.emoji;
      document.getElementById("confirm-question-title").textContent = `${currentActionPayload.vendor} sifarişiniz təsdiqlənsin?`;
      document.getElementById("confirm-details-primary").textContent = currentActionPayload.item;
      document.getElementById("confirm-details-secondary").textContent = `Cəmi ${currentActionPayload.price} (${currentActionPayload.vendor} · Wolt)`;
      document.getElementById("btn-confirm-yes").textContent = "Bəli, sifariş et";

      startConfirmation(
        "chef_tantuni_confirm",
        "Chef Tantunidən bir pors Tantuni sifarişiniz təsdiqlənsin? Cəmi səkkiz manat əlli qəpik. Bəli deyin.",
        executeConfirmedAction
      );
    }, 600);
    return;
  }

  // ----------------------------------------------------
  // SCENARIO 3: WOLT PHARMACY (Aptek / Dərman)
  // ----------------------------------------------------
  if (
    lowered.includes("aptek") ||
    lowered.includes("dərman") ||
    lowered.includes("derman") ||
    lowered.includes("kardiomaqnil") ||
    lowered.includes("təzyiq")
  ) {
    currentActionPayload = {
      type: "ORDER_PHARMACY",
      vendor: "Zəfəran Aptek",
      item: "Kardiomaqnil 75 mq",
      price: "6.20 AZN",
      breakdown: "Dərman 4.20 AZN + Wolt Çatdırılma 2.00 AZN",
      emoji: "💊",
      deepLink: "https://wolt.com/az/aze/baku/search?q=kardiomaqnil"
    };

    setTimeout(() => {
      document.getElementById("confirm-avatar-badge").textContent = "💊";
      document.getElementById("confirm-question-title").textContent = "Aptekdən sifarişiniz təsdiqlənsin?";
      document.getElementById("confirm-details-primary").textContent = "Kardiomaqnil 75 mq (Zəfəran Aptek)";
      document.getElementById("confirm-details-secondary").textContent = "Cəmi 6.20 AZN (Wolt Çatdırılma ilə)";
      document.getElementById("btn-confirm-yes").textContent = "Bəli, sifariş et";

      startConfirmation(
        "pharmacy_confirm",
        "Aptekdən kardiomaqnil dərmanı sifarişiniz təsdiqlənsin? Cəmi altı manat iyirmi qəpik. Bəli deyin.",
        executeConfirmedAction
      );
    }, 600);
    return;
  }

  // ----------------------------------------------------
  // SCENARIO 4: TAXI (Wolt Taxi / Şəhər mərkəzinə)
  // ----------------------------------------------------
  if (
    lowered.includes("taksi") ||
    lowered.includes("taxi") ||
    lowered.includes("maşın") ||
    lowered.includes("masin")
  ) {
    currentActionPayload = {
      type: "ORDER_TAXI",
      route: "Nizami küç. → Şəhər mərkəzi",
      car: "Toyota Camry · 10-AB-123",
      driver: "Rəşad M.",
      price: "5.00 AZN",
      eta: "3 dəq"
    };

    setTimeout(() => {
      document.getElementById("confirm-avatar-badge").textContent = "🚕";
      document.getElementById("confirm-question-title").textContent = "Taksi çağırılsın?";
      document.getElementById("confirm-details-primary").textContent = "Nizami küç. → Şəhər mərkəzi";
      document.getElementById("confirm-details-secondary").textContent = "Toyota Camry · Ekonom 5 AZN";
      document.getElementById("btn-confirm-yes").textContent = "Bəli, taksi çağır";

      startConfirmation(
        "taxi_confirm",
        "Nizami küçəsindən şəhər mərkəzinə taksi çağırılsın? Qiymət beş manat. Bəli deyin.",
        executeConfirmedAction
      );
    }, 600);
    return;
  }

  // ----------------------------------------------------
  // SCENARIO 5: REMINDERS / CALENDAR
  // ----------------------------------------------------
  if (
    lowered.includes("xatırla") ||
    lowered.includes("xatirlat") ||
    lowered.includes("yadıma sal") ||
    lowered.includes("yadima sal") ||
    lowered.includes("təqvim") ||
    lowered.includes("teqvim")
  ) {
    setTimeout(() => {
      showScreen("screen-reminders");
      playAzAudio("reminders", "Xatırlatmalarınız ekrandadır.");
    }, 600);
    return;
  }

  // General fallback
  currentActionPayload = {
    type: "GENERAL",
    text: text
  };

  setTimeout(() => {
    document.getElementById("confirm-avatar-badge").textContent = "✦";
    document.getElementById("confirm-question-title").textContent = "Əməliyyat icra edilsin?";
    document.getElementById("confirm-details-primary").textContent = `“${text}”`;
    document.getElementById("confirm-details-secondary").textContent = "HUG Səsli Köməkçi Sistemi";
    document.getElementById("btn-confirm-yes").textContent = "Bəli, icra et";

    startConfirmation("chef_tantuni_confirm", "Əməliyyatı icra edim? Bəli deyin.", executeConfirmedAction);
  }, 600);
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

  playAzAudio(contact.audio_active || "call_sister_active", `${contact.short_name} ilə əlaqə qurulur`);

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

  if (currentActionPayload && currentActionPayload.type === "ORDER_PHARMACY") {
    playAzAudio("pharmacy_active", "Aptekdən sifarişiniz qəbul olundu. Kuryer yoldadır.");
  } else {
    playAzAudio("chef_tantuni_active", "Chef Tantunidən sifarişiniz qəbul olundu. Kuryer yoldadır.");
  }
}

// Wolt Taxi Tracking Workflow
function startTaxiTracking() {
  showScreen("screen-taxi-tracking");
  playAzAudio("taxi_active", "Taksi təsdiqləndi. Toyota Camry üç dəqiqəyə çatır.");
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
      clearInterval(callTimerInterval);
      showScreen("screen-home");
    });
  });

  // 5. Reminders Avatar Button
  const btnReminders = document.getElementById("btn-open-reminders");
  if (btnReminders) {
    btnReminders.addEventListener("click", () => {
      clearConfirmWorkflow();
      showScreen("screen-reminders");
      playAzAudio("reminders", "Xatırlatmalarınız ekrandadır.");
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
      clearConfirmWorkflow();
      showScreen("screen-home");
      playAzAudio("action_cancel", "Əməliyyat ləğv edildi.");
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
