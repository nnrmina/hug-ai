// Thin client for the FastAPI agent (/api/v1). Same origin locally and on Vercel.
import { deviceId } from "./device.js";
import { knownLocation } from "./location.js";
import { getHistory, getSessionId } from "./store.js";

export const API_BASE = "/api/v1";

export class ApiError extends Error {
  constructor(message, status) {
    super(message);
    this.status = status;
  }
}

async function request(path, { method = "GET", json, body, timeoutMs = 25000 } = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeoutMs);
  try {
    const res = await fetch(`${API_BASE}${path}`, {
      method,
      body: json !== undefined ? JSON.stringify(json) : body,
      headers: { "X-HUG-Device": deviceId(), ...(json !== undefined ? { "Content-Type": "application/json" } : {}) },
      signal: controller.signal
    });
    if (res.status === 204) return null;
    const data = await res.json().catch(() => ({}));
    if (!res.ok) {
      const detail = typeof data.detail === "string" ? data.detail : `HTTP ${res.status}`;
      throw new ApiError(detail, res.status);
    }
    return data;
  } catch (err) {
    if (err.name === "AbortError") throw new ApiError("Server cavab vermədi.", 0);
    if (err instanceof ApiError) throw err;
    throw new ApiError("İnternet bağlantısı yoxdur.", 0);
  } finally {
    clearTimeout(timer);
  }
}

export const getCapabilities = () => request("/assistant/capabilities", { timeoutMs: 6000 });

export function sendText(message) {
  return request("/assistant/message", {
    method: "POST",
    json: { message, session_id: getSessionId(), history: getHistory(), ...(knownLocation() || {}) }
  });
}

export function sendVoice(audioBlob, transcriptHint = "") {
  const form = new FormData();
  form.append("audio", audioBlob, "voice.wav");
  form.append("mime_type", audioBlob.type || "audio/wav");
  form.append("session_id", getSessionId());
  form.append("history", JSON.stringify(getHistory()));
  if (transcriptHint) form.append("transcript", transcriptHint);
  const loc = knownLocation();
  if (loc) { form.append("lat", String(loc.lat)); form.append("lon", String(loc.lon)); }
  return request("/assistant/voice", { method: "POST", body: form, timeoutMs: 30000 });
}

export const confirmAction = (id, token) =>
  request(`/assistant/confirm/${encodeURIComponent(id)}`, { method: "POST", json: { action_token: token || null } });

export const cancelAction = (id, token) =>
  request(`/assistant/cancel/${encodeURIComponent(id)}`, { method: "POST", json: { action_token: token || null } });

export const listReminders = () => request("/reminders");
export const updateReminder = (id, patch) =>
  request(`/reminders/${encodeURIComponent(id)}`, { method: "PATCH", json: patch });
export const deleteReminder = (id) => request(`/reminders/${encodeURIComponent(id)}`, { method: "DELETE" });

export const ttsUrl = (text, lang = "az") =>
  `${API_BASE}/tts?text=${encodeURIComponent(text.slice(0, 600))}${lang === "ru" ? "&lang=ru" : ""}`;
export const nearbyPlaces = (lat, lon, type = "pharmacy") =>
  request(`/places/nearby?lat=${lat}&lon=${lon}&type=${encodeURIComponent(type)}`, { timeoutMs: 20000 });

// ---- care: profile, family circle, medicines, check-in, SOS, push ----
export const careState = () => request("/care/state", { timeoutMs: 10000 });
export const saveProfile = (body) => request("/care/profile", { method: "PUT", json: body });
export const addFamily = (body) => request("/care/family", { method: "POST", json: body });
export const removeFamily = (id) => request(`/care/family/${encodeURIComponent(id)}`, { method: "DELETE" });
export const addMedication = (body) => request("/care/medications", { method: "POST", json: body });
export const removeMedication = (id) => request(`/care/medications/${encodeURIComponent(id)}`, { method: "DELETE" });
export const doseTaken = (id) => request(`/care/doses/${encodeURIComponent(id)}/taken`, { method: "POST" });
export const doseSnooze = (id, minutes = 10) =>
  request(`/care/doses/${encodeURIComponent(id)}/snooze`, { method: "POST", json: { minutes } });
export const sendCheckin = (mood, note = "") => request("/care/checkin", { method: "POST", json: { mood, note } });
export const addHealth = (body) => request("/care/health", { method: "POST", json: body });
export const removeHealth = (id) => request(`/care/health/${encodeURIComponent(id)}`, { method: "DELETE" });
export const sendSos = (body) => request("/care/sos", { method: "POST", json: body, timeoutMs: 15000 });
export const cancelSosApi = () => request("/care/sos/cancel", { method: "POST" });
export const subscribeElderPush = (subscription) =>
  request("/care/push/subscribe", { method: "POST", json: { subscription } });
