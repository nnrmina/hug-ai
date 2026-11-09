// Device location: asked only when a feature needs it (SOS, nearest pharmacy). The last fix is
// remembered so weather questions can use it silently once permission has been granted.
const KEY = "hug_last_location";
export const BAKU = { lat: 40.4093, lon: 49.8671 };
let granted = false;

try {
  navigator.permissions?.query({ name: "geolocation" }).then((p) => {
    granted = p.state === "granted";
    p.onchange = () => { granted = p.state === "granted"; };
  }).catch(() => {});
} catch (_) {}

function remember(loc) {
  try { localStorage.setItem(KEY, JSON.stringify({ ...loc, t: Date.now() })); } catch (_) {}
}

// Last known location (≤ 6 h old), only if the user already allowed location access
export function knownLocation() {
  if (!granted) return null;
  try {
    const l = JSON.parse(localStorage.getItem(KEY) || "null");
    if (l && Date.now() - l.t < 6 * 3600 * 1000) return { lat: l.lat, lon: l.lon };
  } catch (_) {}
  return null;
}

export function getLocation({ timeout = 8000 } = {}) {
  return new Promise((resolve) => {
    if (!navigator.geolocation) return resolve(null);
    navigator.geolocation.getCurrentPosition(
      (p) => {
        const loc = { lat: p.coords.latitude, lon: p.coords.longitude, accuracy: p.coords.accuracy };
        granted = true;
        remember(loc);
        resolve(loc);
      },
      () => resolve(null),
      { enableHighAccuracy: true, timeout, maximumAge: 60000 }
    );
  });
}
