// HUG — voice assistant for elderly people in Azerbaijan.
// Voice / typed command → FastAPI agent (Gemini or rules) → confirmation → on-device action.
import { getCapabilities } from "./api.js";
import { stopSpeaking, unlockAudio, isSpeaking } from "./audio/tts.js";
import { cancelConfirmed, cancelPendingAction, clearQueuedStep, executeConfirmed, runQueuedStep, stopConfirmListening } from "./flows/assistant.js";
import { endCall, stopCallTimer } from "./flows/call.js";
import { cancelListening, finishListening, processText, startListening } from "./flows/listen.js";
import { finishOrder, stopOrderTimers } from "./flows/orders.js";
import { clearDayFilter, openReminders, refreshReminders } from "./reminders/index.js";
import { initSettings } from "./settings.js";
import { ensureNotifications, handleCareDeepLink, initCare, refreshCare, settleOnboarding, showOnboardingEarly, showCheckin, watchDoses } from "./care/care.js";
import { applySettings, capabilities, settings } from "./store.js";
import { haptic } from "./ui/haptics.js";
import { bindWaveform } from "./ui/orb.js";
import { showScreen } from "./ui/screens.js";
import { toast } from "./ui/toast.js";

const on = (id, event, fn) => document.getElementById(id)?.addEventListener(event, fn);

function goHome() {
  clearQueuedStep();
  cancelListening();
  stopConfirmListening();
  cancelPendingAction();
  stopSpeaking();
  stopCallTimer();
  stopOrderTimers();
  showScreen("screen-home");
}

function startClock() {
  const el = document.getElementById("status-clock");
  if (!el) return;
  const update = () => {
    const b = new Date(Date.now() + 4 * 3600 * 1000);
    el.textContent = `${String(b.getUTCHours()).padStart(2, "0")}:${String(b.getUTCMinutes()).padStart(2, "0")}`;
  };
  update();
  setInterval(update, 15000);
}

function greeting() {
  const h = new Date(Date.now() + 4 * 3600 * 1000).getUTCHours();
  const el = document.getElementById("greeting-line");
  if (!el) return;
  el.textContent = h < 5 ? "Gecəniz xeyrə" : h < 12 ? "Sabahınız xeyir" : h < 18 ? "Günortanız xeyir" : "Axşamınız xeyir";
}

async function loadCapabilities() {
  try {
    Object.assign(capabilities, await getCapabilities());
  } catch (_) { /* offline: keep defaults (browser speech + rules) */ }
  const badge = document.getElementById("engine-badge");
  if (badge) {
    const gemini = capabilities.engine === "gemini";
    badge.hidden = false;
    badge.dataset.engine = capabilities.engine;
    badge.textContent = gemini ? "✦ Gemini AI" : "Sadə rejim";
  }
}

function registerServiceWorker() {
  if (!("serviceWorker" in navigator)) return;
  if (location.hostname !== "localhost" && location.hostname !== "127.0.0.1" && location.protocol !== "https:") return;
  // After a deploy the new service worker takes over: reload once so the page runs the new code
  const hadController = Boolean(navigator.serviceWorker.controller);
  navigator.serviceWorker.addEventListener("controllerchange", () => {
    if (!hadController) return; // first install, page is already current
    try {
      if (sessionStorage.getItem("hug_sw_reloaded") === "1") return;
      sessionStorage.setItem("hug_sw_reloaded", "1");
    } catch (_) {}
    location.reload();
  });
  window.addEventListener("load", () => setTimeout(() => {
    try { sessionStorage.removeItem("hug_sw_reloaded"); } catch (_) {}
  }, 10000));
  navigator.serviceWorker.register("/sw.js").then((reg) => reg.update?.()).catch(() => {});
  navigator.serviceWorker.addEventListener("message", (e) => {
    if (e.data?.type === "open-reminders") openReminders();
  });
}

document.addEventListener("DOMContentLoaded", () => {
  applySettings();
  window.matchMedia?.("(prefers-color-scheme: dark)").addEventListener?.("change", applySettings);
  bindWaveform();
  startClock();
  greeting();
  initSettings();
  initCare();
  loadCapabilities();
  registerServiceWorker();
  if (settings.alerts) refreshReminders().catch(() => {});
  const params = new URLSearchParams(location.search);
  showOnboardingEarly();
  refreshCare().then(async (care) => {
    if (settleOnboarding()) return;
    if (params.get("open") === "reminders") return openReminders();
    if (params.get("dose") || params.get("checkin")) return handleCareDeepLink(params);
    if (care && typeof Notification !== "undefined" && Notification.permission === "granted") ensureNotifications({ quiet: true });
  });
  watchDoses();
  navigator.serviceWorker?.addEventListener("message", (e) => {
    if (e.data?.type === "deeplink") handleCareDeepLink(new URLSearchParams(e.data.search || ""));
  });

  document.addEventListener("pointerdown", unlockAudio, { once: true });

  // Home
  on("ai-orb-btn", "click", () => startListening());
  on("btn-tap-to-talk", "click", () => startListening());
  on("text-command-form", "submit", (e) => {
    e.preventDefault();
    const input = document.getElementById("text-command-input");
    const value = input.value.trim();
    if (!value) return input.focus();
    input.value = "";
    unlockAudio();
    processText(value);
  });
  on("btn-open-reminders", "click", () => openReminders());
  on("btn-open-contacts", "click", () => document.getElementById("contacts-dialog")?.showModal());
  on("btn-close-contacts", "click", () => document.getElementById("contacts-dialog")?.close());

  // Listening
  on("btn-finish-recording", "click", () => finishListening());
  on("btn-retry-listening", "click", () => startListening());

  // Confirmation
  on("btn-confirm-yes", "click", () => executeConfirmed());
  on("btn-confirm-cancel", "click", () => cancelConfirmed());

  // Reply / call / orders
  on("btn-reply-talk", "click", () => startListening());
  // Interrupt: tapping the answer while HUG is still talking stops it and opens the mic
  document.querySelector("#screen-reply .reply-main")?.addEventListener("click", (e) => {
    if (e.target.closest("button, a")) return;
    if (isSpeaking()) startListening({ followUp: true });
  });
  on("btn-end-active-call", "click", () => endCall());
  on("btn-order-finish", "click", () => finishOrder());
  on("btn-cancel-taxi", "click", () => {
    goHome();
    toast("Taksi sifarişi ləğv edildi");
  });
  on("btn-clear-day", "click", () => clearDayFilter());
  on("next-step-chip", "click", () => { stopCallTimer(); runQueuedStep(); });

  document.querySelectorAll(".btn-go-home").forEach((b) => b.addEventListener("click", goHome));

  // Keyboard: Escape goes home from any screen (dialogs handle their own Escape)
  document.addEventListener("keydown", (e) => {
    if (e.key === "Escape" && !document.querySelector("dialog[open]")) goHome();
  });

  // Back to the app after a phone call / Wolt: refresh alerts, close stale state
  document.addEventListener("visibilitychange", () => {
    if (document.visibilityState === "visible" && settings.alerts) refreshReminders().catch(() => {});
  });

  window.addEventListener("online", () => toast("İnternet bərpa olundu", { type: "success" }));
  window.addEventListener("offline", () => {
    haptic("warning");
    toast("İnternet yoxdur — əmrlər işləməyəcək", { type: "error", duration: 5000 });
  });
});
