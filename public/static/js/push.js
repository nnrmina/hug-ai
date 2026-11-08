// Web Push subscription (elder or family). Works with the app closed on Android Chrome;
// on iPhone only after "Add to Home Screen" (iOS 16.4+).

function urlBase64ToUint8Array(base64) {
  const padding = "=".repeat((4 - (base64.length % 4)) % 4);
  const raw = atob((base64 + padding).replace(/-/g, "+").replace(/_/g, "/"));
  return Uint8Array.from([...raw].map((c) => c.charCodeAt(0)));
}

export const pushSupported = () => "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;

export async function ensurePushSubscription(publicKey, save) {
  if (!pushSupported() || !publicKey) return { ok: false, reason: "unsupported" };
  const permission = Notification.permission === "default" ? await Notification.requestPermission() : Notification.permission;
  if (permission !== "granted") return { ok: false, reason: permission };
  const reg = (await navigator.serviceWorker.getRegistration()) || (await navigator.serviceWorker.register("/sw.js"));
  await navigator.serviceWorker.ready;
  let sub = await reg.pushManager.getSubscription();
  if (!sub) {
    sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: urlBase64ToUint8Array(publicKey) });
  }
  await save(sub.toJSON());
  return { ok: true };
}
