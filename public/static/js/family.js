// Family view: a relative's private page (/f/<token>). Shows the elder's day, delivers push
// alerts (SOS, missed medicine, bad/missing check-in) and lets the family add medicines.
import { ensurePushSubscription, pushSupported } from "./push.js";
import { toast } from "./ui/toast.js";

const token = location.pathname.split("/f/")[1]?.split("/")[0] || "";
const API = `/api/v1/family/${encodeURIComponent(token)}`;
const $ = (id) => document.getElementById(id);
const MOOD = { good: "😊 Özünü yaxşı hiss edir", ok: "😐 Elə də", bad: "😟 Özünü pis hiss edir" };
const STATUS = { taken: ["İçilib ✓", "ok"], missed: ["İçilməyib", "bad"], pending: ["Gözləyir", "wait"] };
let data = null;

async function api(path = "", options = {}) {
  const res = await fetch(API + path, {
    ...options,
    headers: options.body ? { "Content-Type": "application/json" } : undefined
  });
  if (res.status === 204) return null;
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(typeof body.detail === "string" ? body.detail : `HTTP ${res.status}`);
  return body;
}

const bakuTime = (iso) => {
  const d = new Date(new Date(iso).getTime() + 4 * 3600 * 1000);
  const hm = `${String(d.getUTCHours()).padStart(2, "0")}:${String(d.getUTCMinutes()).padStart(2, "0")}`;
  const today = new Date(Date.now() + 4 * 3600 * 1000);
  return d.getUTCDate() === today.getUTCDate() && d.getUTCMonth() === today.getUTCMonth() ? hm : `${d.getUTCDate()}.${String(d.getUTCMonth() + 1).padStart(2, "0")} ${hm}`;
};

function row(text, badge, kind) {
  const el = document.createElement("div");
  el.className = "family-row-item";
  const t = document.createElement("span");
  t.textContent = text;
  el.append(t);
  if (badge) {
    const b = document.createElement("span");
    b.className = `family-chip ${kind || ""}`;
    b.textContent = badge;
    el.append(b);
  }
  return el;
}

function render() {
  const elder = data.elder.name || "Yaxınınız";
  document.title = `HUG · ${elder}`;
  $("fam-elder").textContent = elder;
  $("fam-hello").textContent = `Salam, ${data.member.name}! Burada ${elder} haqqında bu günün xəbərləri var.`;

  const c = data.checkin;
  $("fam-checkin").textContent = c ? `${MOOD[c.mood] || c.mood} · ${bakuTime(c.at)}`
    : data.checkin_due ? "⏳ Bu gün hələ cavab verməyib" : `Gündəlik sual saat ${data.elder.checkin_time}-da veriləcək`;
  $("fam-checkin").className = `family-big ${c?.mood === "bad" || (!c && data.checkin_due) ? "warn" : ""}`;

  const doses = $("fam-doses");
  doses.innerHTML = "";
  if (!data.doses.length) doses.append(row("Bu gün dərman yoxdur"));
  for (const d of data.doses) {
    const [label, kind] = STATUS[d.status] || [d.status, ""];
    doses.append(row(`${d.time} · ${d.name}${d.dose ? " (" + d.dose + ")" : ""}`, label, kind));
  }

  const meds = $("fam-meds");
  meds.innerHTML = "";
  for (const m of data.medications) {
    const el = row(`${m.name} — hər gün ${m.times.join(", ")}`);
    const del = document.createElement("button");
    del.className = "family-del";
    del.textContent = "✕";
    del.setAttribute("aria-label", `${m.name} — sil`);
    del.addEventListener("click", async () => {
      await api(`/medications/${m.id}`, { method: "DELETE" }).catch(() => {});
      load();
    });
    el.append(del);
    meds.append(el);
  }

  const health = $("fam-health");
  health.innerHTML = "";
  const hlabel = { bp: "Təzyiq", sugar: "Şəkər", pulse: "Nəbz", temp: "Hərarət", weight: "Çəki" };
  const hlevel = { normal: ["Normal", "ok"], high: ["Yüksək", "wait"], low: ["Aşağı", "wait"], critical: ["Diqqət!", "bad"] };
  if (!(data.health || []).length) health.append(row("Hələ qeyd yoxdur"));
  for (const h of (data.health || []).slice(0, 6)) {
    const [label, kind] = hlevel[h.level] || ["", ""];
    health.append(row(`${hlabel[h.kind] || h.kind} ${h.text} · ${bakuTime(h.at)}`, label, kind));
  }

  const events = $("fam-events");
  events.innerHTML = "";
  if (!data.events.length) events.append(row("Hələ hadisə yoxdur"));
  const icon = { health: "❤️", sos: "🚨", dose_missed: "💊", dose_taken: "✓", checkin: "☀️", checkin_missed: "☎️" };
  for (const e of data.events.slice(0, 15)) {
    events.append(row(`${icon[e.kind] || "•"} ${e.message}`, bakuTime(e.at), ["sos", "dose_missed", "health"].includes(e.kind) ? "bad" : ""));
  }

  const sos = data.events.find((e) => e.kind === "sos" && Date.now() - new Date(e.at).getTime() < 24 * 3600 * 1000);
  $("fam-sos").hidden = !sos;
  if (sos) {
    $("fam-sos-text").textContent = `${bakuTime(sos.at)} — ${sos.message}`;
    const map = $("fam-sos-map");
    map.hidden = sos.lat == null;
    if (sos.lat != null) map.href = `https://maps.google.com/?q=${sos.lat},${sos.lon}`;
  }
}

async function load() {
  if (!token) {
    $("fam-elder").textContent = "Keçid səhvdir";
    return;
  }
  try {
    data = await api();
    render();
    updateNotifyButton();
  } catch (err) {
    $("fam-elder").textContent = "Keçid etibarsızdır";
    $("fam-hello").textContent = err.message;
  }
}

async function updateNotifyButton() {
  const btn = $("fam-notify");
  const hint = $("fam-notify-hint");
  if (!data?.push?.enabled) return;
  if (!pushSupported()) {
    hint.hidden = false;
    hint.textContent = /iPhone|iPad/.test(navigator.userAgent)
      ? "iPhone-da bildiriş üçün: Paylaş → “Ana ekrana əlavə et”, sonra oradan açın."
      : "Bu brauzer bildirişləri dəstəkləmir.";
    return;
  }
  const reg = await navigator.serviceWorker.getRegistration();
  const sub = await reg?.pushManager.getSubscription();
  const on = Notification.permission === "granted" && sub;
  btn.hidden = Boolean(on);
  hint.hidden = !on;
  if (on) hint.textContent = "🔔 Bildirişlər açıqdır: SOS, buraxılmış dərman və pis əhval barədə dərhal xəbər alacaqsınız.";
}

$("fam-notify").addEventListener("click", async () => {
  try {
    const r = await ensurePushSubscription(data.push.public_key, (subscription) =>
      api("/push/subscribe", { method: "POST", body: JSON.stringify({ subscription }) }));
    toast(r.ok ? "Bildirişlər açıldı 🔔" : "İcazə verilmədi — brauzer ayarlarından açın", { type: r.ok ? "success" : "error" });
  } catch (err) {
    toast(err.message || "Alınmadı", { type: "error" });
  }
  updateNotifyButton();
});

$("fam-med-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  const times = $("fm-times").value.split(/[,\s]+/).map((t) => t.trim()).filter(Boolean);
  try {
    await api("/medications", { method: "POST", body: JSON.stringify({ name: $("fm-name").value.trim(), times }) });
    e.target.reset();
    toast("Dərman əlavə edildi ✓ — vaxtı gələndə xatırladılacaq", { type: "success" });
  } catch (err) {
    toast(err.message, { type: "error" });
  }
  load();
});

$("fam-rem-form").addEventListener("submit", async (e) => {
  e.preventDefault();
  try {
    await api("/reminders", { method: "POST", body: JSON.stringify({ title: $("fr-title").value.trim(), scheduled_at: $("fr-when").value }) });
    e.target.reset();
    toast("Xatırlatma əlavə edildi ✓", { type: "success" });
  } catch (err) {
    toast(err.message, { type: "error" });
  }
  load();
});

if ("serviceWorker" in navigator) navigator.serviceWorker.register("/sw.js").catch(() => {});
load();
setInterval(() => document.visibilityState === "visible" && load(), 30000);
