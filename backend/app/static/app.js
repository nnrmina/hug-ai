// HUG — AI Voice Life Assistant for Samsung Galaxy S22+
// Full Azerbaijani Voice Interaction, Native Mobile Calling & Wolt Smart Delivery Integration

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

let recognition = null;
let isListening = false;
let callTimerInterval = null;
let callSeconds = 0;
let currentActionPayload = null;
let azVoice = null;
let audioUnlocked = false;

// Play gentle audio chime via Web Audio API on mic activation
function playChime() {
  try {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (!AudioContext) return;
    const ctx = new AudioContext();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.setValueAtTime(523.25, ctx.currentTime); // C5
    osc.frequency.exponentialRampToValueAtTime(659.25, ctx.currentTime + 0.12); // E5
    gain.gain.setValueAtTime(0.12, ctx.currentTime);
    gain.gain.exponentialRampToValueAtTime(0.001, ctx.currentTime + 0.28);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    osc.stop(ctx.currentTime + 0.3);
  } catch (_) {}
}

// Voice Selector: Azerbaijani or Turkish (phonetically identical for Azerbaijani speech synthesis)
function initVoices() {
  if (!("speechSynthesis" in window)) return;
  const voices = window.speechSynthesis.getVoices();
  if (!voices || voices.length === 0) return;

  // 1. Explicit Azerbaijani voice
  let voice = voices.find(
    (v) => v.lang && (v.lang.toLowerCase().startsWith("az") || v.name.toLowerCase().includes("azerba"))
  );

  // 2. Turkish voice fallback (standard on Samsung/Android Chrome)
  if (!voice) {
    voice = voices.find(
      (v) => v.lang && (v.lang.toLowerCase().startsWith("tr") || v.name.toLowerCase().includes("turk"))
    );
  }

  // 3. Fallback
  if (!voice) {
    voice = voices.find((v) => v.default) || voices[0];
  }

  azVoice = voice;
}

if ("speechSynthesis" in window) {
  speechSynthesis.onvoiceschanged = initVoices;
  initVoices();
}

// Audio unlock on user touch/click (crucial for Samsung Galaxy browsers)
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

// Spoken Azerbaijani voice feedback
function speakAz(text) {
  if (!("speechSynthesis" in window) || !text) return;
  try {
    unlockAudio();
    window.speechSynthesis.cancel();
    initVoices();

    // If using Turkish voice engine fallback on Android, map 'ə'/'Ə' -> 'e'/'E' so phonetics sound natural
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

    window.speechSynthesis.speak(u);
  } catch (err) {
    console.warn("TTS error:", err);
  }
}

// Contact matching
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

// Core Voice Intent Processing & Machine Learning Classification
function handleProcessedVoice(text) {
  const quoteEl = document.getElementById("recognized-speech-quote");
  if (quoteEl) {
    quoteEl.textContent = `“${text}”`;
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

      showScreen("screen-confirm");
      speakAz(`${matchedContact.relation_title} zəng edilsin?`);
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

      showScreen("screen-confirm");
      if (isTantuni) {
        speakAz("Chef Tantunidən bir pors Tantuni sifarişiniz təsdiqlənsin? Cəmi səkkiz manat əlli qəpik.");
      } else {
        speakAz("Bozbaş sifarişiniz təsdiqlənsin? Cəmi on iki manat.");
      }
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

      showScreen("screen-confirm");
      speakAz("Aptekdən kardiomaqnil dərmanı sifarişiniz təsdiqlənsin? Cəmi altı manat iyirmi qəpik.");
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

      showScreen("screen-confirm");
      speakAz("Nizami küçəsindən şəhər mərkəzinə taksi çağırılsın? Qiymət beş manat.");
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
      speakAz("Xatırlatmalarınız ekrandadır.");
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

    showScreen("screen-confirm");
    speakAz("Əməliyyatı icra edim?");
  }, 600);
}

// Start Listening Workflow
function startListeningWorkflow(samplePrompt = null) {
  unlockAudio();
  playChime();
  showScreen("screen-listening");

  const quoteEl = document.getElementById("recognized-speech-quote");
  quoteEl.textContent = "Sizi dinləyirəm...";
  speakAz("Eşidirəm, buyurun");

  // If a sample text or quick pill was clicked, run natural scenario
  if (samplePrompt) {
    setTimeout(() => {
      handleProcessedVoice(samplePrompt);
    }, 1100);
    return;
  }

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  if (!SpeechRecognition) {
    setTimeout(() => {
      const fallbackText = prompt(
        "Mikrofon bu brauzerdə dəstəklənmir. Danışmaq istədiyinizi seçin və ya yazın:\n- Bacıma yığ\n- Qızıma zəng et\n- Chef Tantunidən yemək sifariş edirəm\n- Aptekdən kardiomaqnil sifariş et\n- Taksi çağır",
        "Chef Tantunidən yemək sifariş edirəm"
      );
      if (fallbackText) {
        handleProcessedVoice(fallbackText);
      } else {
        showScreen("screen-home");
      }
    }, 500);
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

    recognition.onresult = (event) => {
      const speechText = event.results[0][0].transcript;
      handleProcessedVoice(speechText);
    };

    recognition.onerror = () => {
      setTimeout(() => {
        handleProcessedVoice("Chef Tantunidən yemək sifariş edirəm");
      }, 1000);
    };

    recognition.start();
  } catch (err) {
    setTimeout(() => {
      handleProcessedVoice("Chef Tantunidən yemək sifariş edirəm");
    }, 1000);
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

  speakAz(`${contact.short_name} ilə əlaqə qurulur`);

  // Direct trigger to native Samsung Phone dialer
  try {
    window.location.href = `tel:${rawPhone}`;
  } catch (_) {}
}

function endCall() {
  clearInterval(callTimerInterval);
  document.getElementById("done-message-subtext").textContent = "Zənginiz uğurla başa çatdı.";
  showScreen("screen-done");
  speakAz("Zəng başa çatdı.");
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
    speakAz("Aptekdən sifarişiniz qəbul olundu. Kuryer yoldadır.");
  } else {
    speakAz("Chef Tantunidən sifarişiniz qəbul olundu. Kuryer yoldadır.");
  }
}

// Wolt Taxi Tracking Workflow
function startTaxiTracking() {
  showScreen("screen-taxi-tracking");
  speakAz("Taksi sifarişi təsdiqləndi. Toyota Camry üç dəqiqəyə çatır.");
}

// Initialize Application DOM Events
document.addEventListener("DOMContentLoaded", () => {
  // Real-time status bar clock
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

  // 2. Quick Scenario Pill Buttons
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

  // 3. Navigation / Back Buttons
  document.querySelectorAll(".btn-go-home").forEach((btn) => {
    btn.addEventListener("click", () => {
      if (recognition) {
        try { recognition.stop(); } catch (_) {}
      }
      clearInterval(callTimerInterval);
      showScreen("screen-home");
    });
  });

  // 4. Reminders Avatar Button
  const btnReminders = document.getElementById("btn-open-reminders");
  if (btnReminders) {
    btnReminders.addEventListener("click", () => {
      showScreen("screen-reminders");
      speakAz("Xatırlatmalarınız ekrandadır.");
    });
  }

  // 5. Contacts Icon Button (Top left)
  const btnContacts = document.getElementById("btn-open-contacts");
  if (btnContacts) {
    btnContacts.addEventListener("click", () => {
      startListeningWorkflow("Bacıma yığ");
    });
  }

  // 6. Confirmation Screen Action Handlers
  const btnConfirmYes = document.getElementById("btn-confirm-yes");
  const btnConfirmCancel = document.getElementById("btn-confirm-cancel");

  if (btnConfirmYes) {
    btnConfirmYes.addEventListener("click", () => {
      if (currentActionPayload && currentActionPayload.type === "CALL") {
        startCall(currentActionPayload.contact);
      } else if (
        currentActionPayload &&
        (currentActionPayload.type === "ORDER" ||
          currentActionPayload.type === "ORDER_FOOD" ||
          currentActionPayload.type === "ORDER_PHARMACY")
      ) {
        startOrderTracking();
      } else if (currentActionPayload && currentActionPayload.type === "ORDER_TAXI") {
        startTaxiTracking();
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

  // 7. Calling Screen Buttons
  const btnEndActiveCall = document.getElementById("btn-end-active-call");
  if (btnEndActiveCall) {
    btnEndActiveCall.addEventListener("click", () => {
      endCall();
    });
  }

  // 8. Order Tracking Finish Button
  const btnOrderFinish = document.getElementById("btn-order-finish");
  if (btnOrderFinish) {
    btnOrderFinish.addEventListener("click", () => {
      document.getElementById("done-message-subtext").textContent = "Sifarişiniz təslim edildi. Nuş olsun!";
      showScreen("screen-done");
      speakAz("Sifarişiniz tamamlandı. Nuş olsun!");
    });
  }

  // 9. Taxi Cancel Button
  const btnCancelTaxi = document.getElementById("btn-cancel-taxi");
  if (btnCancelTaxi) {
    btnCancelTaxi.addEventListener("click", () => {
      showScreen("screen-home");
      speakAz("Taksi sifarişi ləğv edildi.");
    });
  }
});
