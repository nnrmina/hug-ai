// HUG service worker: offline app shell + reminder notification clicks.
// API calls (/api/*) are never cached — the assistant must always be live.
const VERSION = "hug-v3-2026-11-09";
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
  "/static/js/audio/shortanswer.js",
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
  "/static/js/device.js",
  "/static/js/push.js",
  "/static/js/native.js",
  "/static/js/care/care.js",
  "/static/js/family.js",
  "/static/js/location.js",
  "/static/js/i18n.js",
  "/static/js/flows/places.js",
  "/family.html",
  "/static/audio/call_end.mp3",
  "/static/audio/order_done.mp3",
  "/static/audio/action_cancel.mp3",
  "/manifest.webmanifest",
  "/favicon.ico",
  "/icons/logo.png",
  "/icons/logo-96.png",
  "/icons/logo-light-96.png",
  "/icons/favicon-32.png",
  "/icons/icon-192.png",
  "/icons/icon-512.png"
];

self.addEventListener("install", (event) => {
  // cache: "reload" bypasses the browser's HTTP cache, so a new version never precaches old files
  event.waitUntil(
    caches.open(VERSION)
      .then((cache) => cache.addAll(SHELL.map((u) => new Request(u, { cache: "reload" }))))
      .then(() => self.skipWaiting())
  );
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

  // Code (CSS/JS/HTML): network first, so online users always get the deployed version;
  // the cache is only the offline fallback. Media (audio, icons): cache first.
  const isCode = /\.(css|js|html|json|webmanifest)$/.test(url.pathname);
  if (isCode) {
    event.respondWith(
      fetch(req, { cache: "no-cache" })
        .then((res) => {
          if (res.ok) {
            const copy = res.clone();
            caches.open(VERSION).then((c) => c.put(req, copy));
          }
          return res;
        })
        .catch(() => caches.match(req, { ignoreSearch: true }))
    );
    return;
  }
  event.respondWith(
    caches.match(req).then((cached) => cached || fetch(req).then((res) => {
      if (res.ok) {
        const copy = res.clone();
        caches.open(VERSION).then((c) => c.put(req, copy));
      }
      return res;
    }))
  );
});

// Server-sent push: medicine time, reminders, check-in (elder) / SOS, missed doses (family)
self.addEventListener("push", (event) => {
  let data = {};
  try { data = event.data ? event.data.json() : {}; } catch (_) { data = { title: "HUG", body: event.data?.text() || "" }; }
  const title = data.title || "HUG";
  const options = {
    body: data.body || "",
    tag: data.tag || undefined,
    renotify: Boolean(data.tag),
    requireInteraction: Boolean(data.requireInteraction),
    icon: "/icons/icon-192.png",
    badge: "/icons/icon-192.png",
    vibrate: data.kind === "sos" ? [300, 100, 300, 100, 600] : [120, 60, 120],
    actions: Array.isArray(data.actions) ? data.actions.slice(0, 2) : [],
    data: { url: data.url || "/", doseId: data.doseId || null }
  };
  event.waitUntil(self.registration.showNotification(title, options));
});

self.addEventListener("notificationclick", (event) => {
  event.notification.close();
  const data = event.notification.data || {};
  let url = data.url || "/?open=reminders";
  if (data.doseId && (event.action === "taken" || event.action === "snooze")) {
    url = `/?dose=${encodeURIComponent(data.doseId)}&act=${event.action}`;
  }
  const target = new URL(url, location.origin);
  event.waitUntil(
    self.clients.matchAll({ type: "window", includeUncontrolled: true }).then((clients) => {
      // External links (e.g. Google Maps location in an SOS) open in a new window
      if (target.origin !== location.origin) return self.clients.openWindow(target.href);
      const client = clients.find((c) => new URL(c.url).origin === location.origin &&
        (target.pathname.startsWith("/f/") ? new URL(c.url).pathname === target.pathname : !new URL(c.url).pathname.startsWith("/f/")));
      if (client) {
        if (target.search) client.postMessage({ type: "deeplink", search: target.search });
        else client.postMessage({ type: "open-reminders" });
        return client.focus();
      }
      return self.clients.openWindow(target.href);
    })
  );
});
