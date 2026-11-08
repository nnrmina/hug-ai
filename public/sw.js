// HUG service worker: offline app shell + reminder notification clicks.
// API calls (/api/*) are never cached — the assistant must always be live.
const VERSION = "hug-v2-2026-11-09";
const SHELL = [
  "/",
  "/static/styles.css",
  "/static/js/main.js",
  "/static/js/api.js",
  "/static/js/store.js",
  "/static/js/contacts.js",
  "/static/js/settings.js",
  "/static/js/audio/tts.js",
  "/static/js/audio/recorder.js",
  "/static/js/audio/webspeech.js",
  "/static/js/ui/screens.js",
  "/static/js/ui/toast.js",
  "/static/js/ui/haptics.js",
  "/static/js/ui/orb.js",
  "/static/js/flows/assistant.js",
  "/static/js/flows/listen.js",
  "/static/js/flows/call.js",
  "/static/js/flows/orders.js",
  "/static/js/reminders/index.js",
  "/static/js/reminders/calendar.js",
  "/static/js/reminders/alerts.js",
  "/static/audio/call_end.mp3",
  "/static/audio/order_done.mp3",
  "/static/audio/action_cancel.mp3",
  "/manifest.webmanifest",
  "/favicon.svg",
  "/icons/icon-192.png",
  "/icons/icon-512.png"
];

self.addEventListener("install", (event) => {
  event.waitUntil(caches.open(VERSION).then((cache) => cache.addAll(SHELL)).then(() => self.skipWaiting()));
});

self.addEventListener("activate", (event) => {
  event.waitUntil(
    caches.keys()
      .then((keys) => Promise.all(keys.filter((k) => k !== VERSION).map((k) => caches.delete(k))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener("fetch", (event) => {
  const req = event.request;
  const url = new URL(req.url);
  if (req.method !== "GET" || url.origin !== location.origin || url.pathname.startsWith("/api/")) return;

  // Pages: network first so updates land immediately; cached shell when offline
  if (req.mode === "navigate") {
    event.respondWith(
      fetch(req)
        .then((res) => {
          const copy = res.clone();
          caches.open(VERSION).then((c) => c.put("/", copy));
          return res;
        })
        .catch(() => caches.match("/"))
    );
    return;
  }

  // Static assets: stale-while-revalidate
  event.respondWith(
    caches.match(req).then((cached) => {
      const network = fetch(req)
        .then((res) => {
          if (res.ok) caches.open(VERSION).then((c) => c.put(req, res.clone()));
          return res;
        })
        .catch(() => cached);
      return cached || network;
    })
  );
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      const client = clients.find((c) => new URL(c.url).origin === location.origin);
      if (client) {
        client.postMessage({ type: "open-reminders" });
        return client.focus();
      }
      return self.clients.openWindow("/?open=reminders");
    })
  );
});
