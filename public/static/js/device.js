// Anonymous per-phone identity (no login). Generated once, kept in localStorage, sent as
// X-HUG-Device so each phone only sees its own reminders, medicines and family circle.
const KEY = "hug_device_id";

function make() {
  if (crypto.randomUUID) return crypto.randomUUID();
  const b = crypto.getRandomValues(new Uint8Array(16));
  return [...b].map((x) => x.toString(16).padStart(2, "0")).join("").replace(/(.{8})(.{4})(.{4})(.{4})(.{12})/, "$1-$2-$3-$4-$5");
}

let id = null;
try { id = localStorage.getItem(KEY); } catch (_) {}
if (!id) {
  id = make();
  try { localStorage.setItem(KEY, id); } catch (_) {}
}

export const deviceId = () => id;
