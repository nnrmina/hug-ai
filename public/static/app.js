// HUG — Resilient Voice Agent with Live Mic Visualizer & Multi-Engine Speech Recognition

const INITIAL_CONTACTS = [
  { alias: "mama", display_name: "Anam (Mama)", phone_number: "+994 55 234 56 78" },
  { alias: "anam", display_name: "Anam (Mama)", phone_number: "+994 55 234 56 78" },
  { alias: "almaz", display_name: "Almaz Məmmədova", phone_number: "+994 50 456 78 90" },
  { alias: "almaz xala", display_name: "Almaz Xala", phone_number: "+994 50 456 78 90" },
  { alias: "qızım", display_name: "Aysel İbrahimova (Qızım)", phone_number: "+994 50 123 45 67" },
  { alias: "aysel", display_name: "Aysel İbrahimova", phone_number: "+994 50 123 45 67" },
  { alias: "oğlum", display_name: "Orxan İbrahimov (Oğlum)", phone_number: "+994 70 345 67 89" },
  { alias: "kamran", display_name: "Kamran Əliyev", phone_number: "+994 50 765 43 21" },
  { alias: "leyla", display_name: "Leyla Həsənova", phone_number: "+994 55 987 65 43" }
];

let recognition = null;
let isListening = false;
let isExecuting = false;
let callTimer = null;
let micAudioStream = null;
let audioContext = null;
let analyser = null;
let animFrameId = null;

function getContacts() {
  const raw = localStorage.getItem("yaxin_orb_contacts");
  if (!raw) {
    localStorage.setItem("yaxin_orb_contacts", JSON.stringify(INITIAL_CONTACTS));
    return [...INITIAL_CONTACTS];
  }
  try {
    return JSON.parse(raw);
  } catch {
    return [...INITIAL_CONTACTS];
  }
}

function saveContacts(list) {
  localStorage.setItem("yaxin_orb_contacts", JSON.stringify(list));
}

function setStatus(text, isError = false) {
  const el = document.getElementById("live-status-text");
  if (!el) return;
  el.textContent = text;
  el.style.color = isError ? "#dc2626" : "#2e7d32";
}

function normalizeAzTargetName(raw) {
  if (!raw) return "";
  let s = raw
    .trim()
    .toLowerCase()
    .replace(/^(salam\s+)?(yaxın|yaxin|hug)[\s,!]*/i, "")
    .replace(/\s*(üçün\s+)?(zəng\s*et|zeng\s*et|zəng\s*elə|zeng\s*ele|zəng\s*vur|zeng\s*vur|zəng|zeng|yığ|yig).*$/i, "")
    .trim();

  if (s === "mamama" || s === "mamaya" || s === "mama") return "mama";
  if (s === "anama" || s === "anaya" || s === "ana") return "anam";
  if (s === "qızıma" || s === "qizima") return "qızım";

  if (s.length > 4 && (s.endsWith("ya") || s.endsWith("yə"))) {
    return s.slice(0, -2);
  }
  const vowelNames = new Set(["leyla", "fatimə", "zəhra", "səbinə", "nərminə", "narmina", "əli", "sevda", "vəfa", "mama"]);
  if (s.length > 3 && (s.endsWith("a") || s.endsWith("ə")) && !vowelNames.has(s)) {
    return s.slice(0, -1);
  }
  return s;
}

function findContact(query) {
  const list = getContacts();
  const norm = normalizeAzTargetName(query);
  const raw = (query || "").trim().toLowerCase();

  for (const c of list) {
    const a = c.alias.toLowerCase();
    const n = c.display_name.toLowerCase();
    if (a === raw || a === norm || n.includes(norm) || a.includes(norm) || norm.includes(a)) {
      return c;
    }
  }
  return null;
}

function speakAz(text) {
  if (!("speechSynthesis" in window)) return;
  try {
    window.speechSynthesis.cancel();
    const u = new SpeechSynthesisUtterance(text);
    u.lang = "az-AZ";
    u.rate = 0.95;
    window.speechSynthesis.speak(u);
  } catch (_) {}
}

function playRingTone() {
  try {
    const ctx = new (window.AudioContext || window.webkitAudioContext)();
    const osc = ctx.createOscillator();
    const gain = ctx.createGain();
    osc.type = "sine";
    osc.frequency.setValueAtTime(425, ctx.currentTime);
    gain.gain.setValueAtTime(0.06, ctx.currentTime);
    osc.connect(gain);
    gain.connect(ctx.destination);
    osc.start();
    setTimeout(() => {
      try { osc.stop(); } catch (_) {}
    }, 600);
  } catch (_) {}
}

const wait = ms => new Promise(r => setTimeout(r, ms));

// AI Agent Execution Pipeline
async function executeAiAgent(commandText) {
  const text = (commandText || "").trim();
  if (!text || isExecuting) return;

  isExecuting = true;
  stopMicVisualizer();
  if (recognition) {
    try { recognition.abort(); } catch (_) {}
  }

  const pillText = document.getElementById("agent-pill-text");
  const orb = document.getElementById("ai-orb-btn");

  orb.classList.remove("listening");
  orb.classList.add("executing");
  pillText.textContent = "HUG icra edir...";
  setStatus(`"${text}"`);

  let targetPerson = normalizeAzTargetName(text);

  try {
    const resp = await fetch("/api/v1/assistant/message", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message: text })
    });
    const data = await resp.json();
    if (data.action_data && data.action_data.contact_alias) {
      targetPerson = data.action_data.contact_alias;
    }
    if (data.action_id) {
      fetch(`/api/v1/assistant/confirm/${data.action_id}`, { method: "POST" }).catch(() => {});
    }
  } catch (_) {}

  await wait(400);

  let matched = findContact(targetPerson);
  if (!matched) {
    const formattedName = targetPerson
      ? targetPerson.charAt(0).toUpperCase() + targetPerson.slice(1)
      : "Mama";
    matched = {
      alias: formattedName.toLowerCase(),
      display_name: formattedName,
      phone_number: "+994 55 234 56 78"
    };
    const list = getContacts();
    list.unshift(matched);
    saveContacts(list);
  }

  setStatus(`${matched.display_name} tapıldı · Zəng edilir...`);
  pillText.textContent = "Zəng edilir";
  speakAz(`${matched.display_name} tapıldı. Zəng edilir.`);

  await wait(400);
  orb.classList.remove("executing");
  openCallOverlay(matched);
}

function openCallOverlay(contact) {
  const overlay = document.getElementById("call-overlay");
  document.getElementById("call-avatar").textContent = contact.display_name.charAt(0).toUpperCase();
  document.getElementById("call-name").textContent = contact.display_name;
  document.getElementById("call-number").textContent = contact.phone_number;
  document.getElementById("native-tel-link").href = `tel:${contact.phone_number.replace(/\s+/g, "")}`;

  const stateEl = document.getElementById("call-state-text");
  stateEl.textContent = "Nömrə yığılır...";
  overlay.classList.remove("hidden");

  playRingTone();
  let sec = 0;
  clearInterval(callTimer);
  callTimer = setInterval(() => {
    sec++;
    if (sec < 3) {
      stateEl.textContent = "Zəng gedir...";
    } else {
      const m = String(Math.floor((sec - 2) / 60)).padStart(2, "0");
      const s = String((sec - 2) % 60).padStart(2, "0");
      stateEl.textContent = `Danışıq gedir · ${m}:${s}`;
    }
  }, 1000);
}

function closeCallOverlay() {
  clearInterval(callTimer);
  document.getElementById("call-overlay").classList.add("hidden");
  document.getElementById("agent-pill-text").textContent = "HUG";
  setStatus("");
  isExecuting = false;
  // Automatically resume listening
  startListening();
}

// Live Microphone Waveform Visualizer on the Orb
async function startMicVisualizer() {
  try {
    if (!micAudioStream) {
      micAudioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    }
    audioContext = new (window.AudioContext || window.webkitAudioContext)();
    const source = audioContext.createMediaStreamSource(micAudioStream);
    analyser = audioContext.createAnalyser();
    analyser.fftSize = 64;
    source.connect(analyser);

    const dataArray = new Uint8Array(analyser.frequencyBinCount);
    const orb = document.getElementById("ai-orb-btn");

    function update() {
      if (!isListening) return;
      analyser.getByteFrequencyData(dataArray);
      let sum = 0;
      for (let i = 0; i < dataArray.length; i++) sum += dataArray[i];
      const avg = sum / dataArray.length;
      const scale = 1 + Math.min(avg / 180, 0.25);
      if (orb) {
        orb.style.transform = `scale(${scale})`;
      }
      animFrameId = requestAnimationFrame(update);
    }
    update();
  } catch (err) {
    console.warn("AudioContext visualizer not available:", err);
  }
}

function stopMicVisualizer() {
  if (animFrameId) cancelAnimationFrame(animFrameId);
  const orb = document.getElementById("ai-orb-btn");
  if (orb) orb.style.transform = "scale(1)";
}

// Robust Speech Recognition
async function startListening() {
  if (isExecuting) return;

  const orb = document.getElementById("ai-orb-btn");
  const pillText = document.getElementById("agent-pill-text");

  // 1. Check if in Secure Context (localhost, 127.0.0.1 or HTTPS)
  if (!window.isSecureContext && location.hostname !== "localhost" && location.hostname !== "127.0.0.1") {
    setStatus("⚠️ Mikrofon üçün kompyuterdə 'http://localhost:8000/app' açın (və ya HTTPS istifadə edin).", true);
  }

  try {
    if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
      if (!micAudioStream) {
        setStatus("Mikrofon aktivləşdirilir...");
        micAudioStream = await navigator.mediaDevices.getUserMedia({ audio: true });
      }
    }
  } catch (micErr) {
    console.warn("getUserMedia error:", micErr);
    setStatus("⚠️ Mikrofon bloklanıb. Ünvan sətrindəki 'Not secure' / qıfıl ikonuna basıb 'Microphone: Allow' edin.", true);
  }

  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;

  if (!SpeechRecognition) {
    setStatus("Brauzer Speech-to-Text dəstəkləmir. Kürəyə basaraq test edin.");
    return;
  }

  if (recognition) {
    try { recognition.abort(); } catch (_) {}
  }

  recognition = new SpeechRecognition();
  recognition.lang = "az-AZ";
  recognition.continuous = true;
  recognition.interimResults = true;
  recognition.maxAlternatives = 1;

  isListening = true;
  orb.classList.add("listening");
  pillText.textContent = "Dinləyirəm...";
  setStatus("🎙️ Dinlənilir... Danışın (məs: 'Mamama zəng et')");

  startMicVisualizer();

  let detectedTranscript = "";

  recognition.onresult = event => {
    let interim = "";
    for (let i = event.resultIndex; i < event.results.length; i++) {
      const t = event.results[i][0].transcript;
      if (event.results[i].isFinal) {
        detectedTranscript = t;
      } else {
        interim += t;
      }
    }
    const current = (detectedTranscript || interim).trim();
    if (current) {
      setStatus(`Eşidildi: "${current}"`);
      const lower = current.toLowerCase();
      if (
        lower.includes("zəng") ||
        lower.includes("zeng") ||
        lower.includes("yığ") ||
        lower.includes("mama") ||
        lower.includes("anam") ||
        lower.includes("almaz")
      ) {
        executeAiAgent(current);
      }
    }
  };

  recognition.onerror = event => {
    console.warn("Speech recognition error:", event.error);
    if (event.error === "not-allowed") {
      setStatus("⚠️ Brauzer mikrofona icazə vermədi. Ünvan sətrindəki icazəni açın.", true);
      isListening = false;
      orb.classList.remove("listening");
      stopMicVisualizer();
    } else if (event.error === "language-not-supported" || event.error === "network") {
      // Try fallback to Turkish or generic if az-AZ is not installed on Windows Speech Engine
      try {
        recognition.lang = "tr-TR";
        recognition.start();
      } catch (_) {}
    }
  };

  recognition.onend = () => {
    if (isListening && !isExecuting) {
      // Auto-restart to stay always listening
      try { recognition.start(); } catch (_) {}
    } else {
      orb.classList.remove("listening");
      stopMicVisualizer();
    }
  };

  try {
    recognition.start();
  } catch (e) {
    console.warn("Recognition start error:", e);
  }
}

function stopListening() {
  isListening = false;
  if (recognition) {
    try { recognition.stop(); } catch (_) {}
  }
  stopMicVisualizer();
  const orb = document.getElementById("ai-orb-btn");
  if (orb) orb.classList.remove("listening");
  document.getElementById("agent-pill-text").textContent = "HUG";
}

function renderContactsList() {
  const listEl = document.getElementById("contacts-list");
  if (!listEl) return;
  const contacts = getContacts();
  listEl.innerHTML = contacts
    .map(
      c => `
      <div class="contact-row">
        <div>
          <strong>${c.display_name}</strong>
          <span>${c.phone_number}</span>
        </div>
        <button class="send-pill-btn" onclick="callContactFromDrawer('${c.alias}')">Zəng et ↑</button>
      </div>
    `
    )
    .join("");
}

window.callContactFromDrawer = function (alias) {
  document.getElementById("contacts-drawer").classList.add("hidden");
  executeAiAgent(`${alias} zəng et`);
};

document.addEventListener("DOMContentLoaded", () => {
  renderContactsList();

  // Clicking the Orb starts/triggers the microphone
  const orb = document.getElementById("ai-orb-btn");
  orb.addEventListener("click", () => {
    if (isListening) {
      // If already listening and user taps again, let's trigger default action or restart
      setStatus("Dinləyirəm, danışın...");
    } else {
      startListening();
    }
  });

  // Also auto-start immediately when page loads
  setTimeout(() => {
    startListening();
  }, 400);

  // If browser requires user interaction first, any tap on the screen triggers listening
  document.body.addEventListener("pointerdown", () => {
    if (!isListening && !isExecuting) {
      startListening();
    }
  }, { once: true });

  document.getElementById("btn-end-call").addEventListener("click", closeCallOverlay);

  const openDrawer = () => {
    renderContactsList();
    document.getElementById("contacts-drawer").classList.remove("hidden");
  };
  document.getElementById("btn-open-contacts").addEventListener("click", openDrawer);
  document.getElementById("btn-new-contact").addEventListener("click", openDrawer);

  document.getElementById("btn-close-drawer").addEventListener("click", () => {
    document.getElementById("contacts-drawer").classList.add("hidden");
    startListening();
  });

  document.getElementById("add-contact-form").addEventListener("submit", e => {
    e.preventDefault();
    const name = document.getElementById("new-name").value.trim();
    const phone = document.getElementById("new-phone").value.trim();
    if (!name || !phone) return;
    const list = getContacts();
    list.unshift({
      alias: name.toLowerCase(),
      display_name: name,
      phone_number: phone
    });
    saveContacts(list);
    e.target.reset();
    renderContactsList();
  });
});
