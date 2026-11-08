// Thin client for the FastAPI agent (/api/v1). Same origin locally and on Vercel.
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
      headers: json !== undefined ? { "Content-Type": "application/json" } : undefined,
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
    json: { message, session_id: getSessionId(), history: getHistory() }
  });
}

export function sendVoice(audioBlob, transcriptHint = "") {
  const form = new FormData();
  form.append("audio", audioBlob, "voice.wav");
  form.append("mime_type", audioBlob.type || "audio/wav");
  form.append("session_id", getSessionId());
  form.append("history", JSON.stringify(getHistory()));
  if (transcriptHint) form.append("transcript", transcriptHint);
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

export const ttsUrl = (text) => `${API_BASE}/tts?text=${encodeURIComponent(text.slice(0, 600))}`;
