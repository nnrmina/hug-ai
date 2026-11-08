// Reminder alerts while the app is open (or installed as a PWA): a system notification via
// the service worker plus a spoken alert. There is no server push, so a fully closed
// browser cannot ring — the settings screen says so.
import { speak } from "../audio/tts.js";
import { bakuParts } from "../flows/assistant.js";
import { settings } from "../store.js";
import { haptic } from "../ui/haptics.js";
import { toast } from "../ui/toast.js";

const FIRED_KEY = "hug_fired_alerts";
const MAX_TIMER_MS = 2 ** 31 - 1;
let timer = null;
let reminders = [];

function fired() {
  try { return new Set(JSON.parse(localStorage.getItem(FIRED_KEY)) || []); } catch (_) { return new Set(); }
}

function markFired(id) {
  const set = fired();
  set.add(id);
  try { localStorage.setItem(FIRED_KEY, JSON.stringify([...set].slice(-200))); } catch (_) {}
}

export function scheduleAlerts(list) {
  reminders = list || reminders;
  clearTimeout(timer);
  if (!settings.alerts) return;

  const done = fired();
  const now = Date.now();
  const upcoming = reminders
    .filter((r) => r.status === "pending" && !done.has(r.id))
    .map((r) => ({ r, at: bakuParts(r.scheduled_at)?.date.getTime() }))
    .filter((x) => x.at)
    .sort((a, b) => a.at - b.at);

  // Anything due in the last 10 minutes that we have not announced yet fires now
  const due = upcoming.filter((x) => x.at <= now && now - x.at < 10 * 60 * 1000);
  if (due.length) {
    due.forEach((x) => fire(x.r));
    return scheduleAlerts();
  }

  const next = upcoming.find((x) => x.at > now);
  if (next) timer = setTimeout(() => scheduleAlerts(), Math.min(next.at - now + 250, MAX_TIMER_MS));
}

async function fire(reminder) {
  markFired(reminder.id);
  haptic("warning");
  const text = `Xatırlatma: ${reminder.title}.`;
  toast(`⏰ ${reminder.title}`, { duration: 10000 });
  speak(text);

  if ("Notification" in window && Notification.permission === "granted") {
    try {
      const reg = await navigator.serviceWorker?.getRegistration();
      const options = {
        body: reminder.title,
        tag: `reminder-${reminder.id}`,
        icon: "/icons/icon-192.png",
        badge: "/icons/icon-192.png",
        requireInteraction: true,
        data: { url: "/" }
      };
      if (reg) await reg.showNotification("HUG · Xatırlatma", options);
      else new Notification("HUG · Xatırlatma", options);
    } catch (_) { /* toast + voice already delivered */ }
  }
}

// Ask for notification permission in context (right after the first reminder is created)
export async function ensureAlertPermission() {
  if (!settings.alerts || !("Notification" in window)) return false;
  if (Notification.permission === "granted") return true;
  if (Notification.permission === "denied") return false;
  try {
    const result = await Notification.requestPermission();
    if (result === "granted") toast("Xatırlatma bildirişləri aktivdir 🔔", { type: "success" });
    return result === "granted";
  } catch (_) {
    return false;
  }
}
