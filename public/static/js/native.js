// Native powers when HUG runs inside the Android app (Capacitor shell); plain web fallbacks otherwise.
//  - directCall: places the call immediately (after the in-app "Bəli"), no dialer step
//  - medicine alarms: native daily notifications that fire even when the app is closed
//    (Android WebView has no Web Push, so this replaces it inside the app)

const cap = () => window.Capacitor;
export const isNativeApp = () => Boolean(cap()?.isNativePlatform?.());
const plugin = (name) => cap()?.Plugins?.[name];

// App 1.1+ can list SIMs; 1.0 cannot (Android then shows its own SIM picker)
export const simChoiceSupported = () => typeof plugin("DirectCall")?.simCards === "function";

// Dual-SIM: the SIMs that can place calls, in slot order → [{ index, slot, carrier }].
// Empty in the browser, on single-SIM phones' older app builds, or without the phone permission.
export async function listSims() {
  const dc = isNativeApp() && plugin("DirectCall");
  if (!dc || typeof dc.simCards !== "function") return [];
  try {
    const { sims } = await dc.simCards();
    return Array.isArray(sims) ? sims : [];
  } catch (_) {
    return []; // app build without simCards(): Android shows its own SIM picker
  }
}

// `sim` = index from listSims(); without it Android uses the default SIM (or asks).
export async function directCall(number, sim) {
  const clean = String(number || "").replace(/[^\d+]/g, "");
  if (!clean) return false;
  const dc = isNativeApp() && plugin("DirectCall");
  if (dc) {
    try {
      await dc.call(Number.isInteger(sim) ? { number: clean, sim } : { number: clean });
      return true;
    } catch (_) { /* fall through to the dialer */ }
  }
  try { window.location.href = `tel:${clean}`; } catch (_) {}
  return false;
}

export async function nativeNotificationsReady() {
  const ln = isNativeApp() && plugin("LocalNotifications");
  if (!ln) return false;
  try {
    let p = await ln.checkPermissions();
    if (p.display !== "granted") p = await ln.requestPermissions();
    return p.display === "granted";
  } catch (_) {
    return false;
  }
}

let lastSignature = "";

// Re-schedule one repeating daily alarm per medicine time. Idempotent (skips when unchanged).
export async function scheduleMedicineAlarms(medications = []) {
  const ln = isNativeApp() && plugin("LocalNotifications");
  if (!ln) return;
  const signature = JSON.stringify(medications.map((m) => [m.id, m.name, m.dose, m.times]));
  if (signature === lastSignature) return;
  if (!(await nativeNotificationsReady())) return;
  lastSignature = signature;
  try {
    const pending = await ln.getPending();
    if (pending.notifications?.length) await ln.cancel({ notifications: pending.notifications.map((n) => ({ id: n.id })) });
    const notifications = [];
    let id = 1000;
    for (const m of medications) {
      for (const t of m.times) {
        const [hour, minute] = t.split(":").map(Number);
        notifications.push({
          id: id++,
          title: "💊 Dərman vaxtıdır",
          body: `${m.name}${m.dose ? " · " + m.dose : ""} — saat ${t}`,
          schedule: { on: { hour, minute }, allowWhileIdle: true },
          extra: { kind: "dose", medicationId: m.id },
          smallIcon: "ic_stat_hug",
          iconColor: "#2ea13f"
        });
      }
    }
    if (notifications.length) await ln.schedule({ notifications });
  } catch (err) {
    console.warn("native alarms failed", err);
  }
}

// Tapping a native alarm opens the medicine screen for the due dose
export function onNativeAlarmTap(handler) {
  const ln = isNativeApp() && plugin("LocalNotifications");
  if (!ln) return;
  ln.addListener("localNotificationActionPerformed", (e) => handler(e?.notification?.extra || {}));
}
