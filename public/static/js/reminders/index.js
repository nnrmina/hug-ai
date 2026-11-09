// Reminders screen: live calendar + list (done / delete with undo), backed by /api/v1/reminders.
import { deleteReminder, listReminders, updateReminder } from "../api.js";
import { speak } from "../audio/tts.js";
import { getLang } from "../i18n.js";
import { bakuParts, formatWhen } from "../flows/assistant.js";
import { haptic } from "../ui/haptics.js";
import { announce, showScreen } from "../ui/screens.js";
import { toast } from "../ui/toast.js";
import { ensureAlertPermission, scheduleAlerts } from "./alerts.js";
import { AZ_MONTHS_TITLE, bakuToday, dayKey, renderCalendar } from "./calendar.js";

const state = {
  reminders: [],
  view: null,          // { year, month }
  selected: null,      // "YYYY-MM-DD" filter
  highlightId: null,
  loaded: false
};

const pendingDeletes = new Map(); // id -> timeout

export async function refreshReminders() {
  try {
    state.reminders = await listReminders();
    state.loaded = true;
  } catch (err) {
    state.loaded = true;
    throw err;
  } finally {
    scheduleAlerts(visibleReminders());
  }
  return state.reminders;
}

function visibleReminders() {
  return state.reminders.filter((r) => !pendingDeletes.has(r.id));
}

export async function openReminders({ spoken, highlightId = null, askAlerts = false, onSpoken = null } = {}) {
  state.highlightId = highlightId;
  if (!state.view) {
    const t = bakuToday();
    state.view = { year: t.y, month: t.m };
  }
  showScreen("screen-reminders");
  renderList({ loading: !state.loaded });
  render();

  try {
    await refreshReminders();
  } catch (err) {
    renderList({ error: true });
    toast("Xatırlatmalar yüklənmədi", { type: "error" });
    return;
  }

  // Jump the calendar to the newly created reminder's month
  const created = highlightId && state.reminders.find((r) => r.id === highlightId);
  if (created) {
    const p = bakuParts(created.scheduled_at);
    if (p) state.view = { year: p.y, month: p.m };
  }
  render();

  const text = spoken || summary();
  announce(text);
  await speak(text, spoken ? getLang() : "az");
  if (askAlerts) ensureAlertPermission();
  onSpoken?.();
}

function summary() {
  const upcoming = upcomingList();
  if (!upcoming.length) return "Hazırda xatırlatmanız yoxdur.";
  const next = upcoming[0];
  return `${upcoming.length} xatırlatmanız var. Növbəti: ${next.title}, ${formatWhen(next.scheduled_at)}.`;
}

function upcomingList() {
  return visibleReminders()
    .filter((r) => r.status === "pending")
    .sort((a, b) => bakuParts(a.scheduled_at).date - bakuParts(b.scheduled_at).date);
}

function render() {
  const cal = document.getElementById("calendar-card");
  if (!cal || !state.view) return;
  const counts = new Map();
  for (const r of upcomingList()) {
    const p = bakuParts(r.scheduled_at);
    if (!p) continue;
    const key = dayKey(p.y, p.m, p.d);
    counts.set(key, (counts.get(key) || 0) + 1);
  }
  renderCalendar(cal, {
    year: state.view.year,
    month: state.view.month,
    selected: state.selected,
    counts,
    onSelect: (key) => {
      state.selected = key;
      haptic("tap");
      render();
    },
    onMonth: (delta) => {
      let { year, month } = state.view;
      month += delta;
      if (month < 0) { month = 11; year -= 1; }
      if (month > 11) { month = 0; year += 1; }
      state.view = { year, month };
      render();
      announce(`${AZ_MONTHS_TITLE[month]} ${year}`);
    }
  });
  renderList();
}

function relative(iso) {
  const p = bakuParts(iso);
  if (!p) return "";
  const diffMin = Math.round((p.date - Date.now()) / 60000);
  if (diffMin < 0) return "keçib";
  if (diffMin < 60) return `${Math.max(1, diffMin)} dəq sonra`;
  const t = bakuToday();
  const days = Math.round((Date.UTC(p.y, p.m, p.d) - Date.UTC(t.y, t.m, t.d)) / 86400000);
  if (days === 0) return `${Math.round(diffMin / 60)} saat sonra`;
  if (days === 1) return "sabah";
  if (days === 2) return "birigün";
  return `${days} gün sonra`;
}

function renderList({ loading = false, error = false } = {}) {
  const list = document.getElementById("reminders-list");
  const heading = document.getElementById("reminders-list-title");
  if (!list) return;
  list.setAttribute("aria-busy", loading ? "true" : "false");

  if (loading) {
    list.innerHTML = '<div class="skeleton-card"></div><div class="skeleton-card"></div>';
    return;
  }
  if (error) {
    list.innerHTML = '<p class="reminders-empty">Xatırlatmalar yüklənmədi. İnternet bağlantısını yoxlayın.</p>';
    return;
  }

  let items = upcomingList();
  if (state.selected) {
    items = items.filter((r) => {
      const p = bakuParts(r.scheduled_at);
      return p && dayKey(p.y, p.m, p.d) === state.selected;
    });
  }
  if (heading) {
    if (state.selected) {
      const [y, m, d] = state.selected.split("-").map(Number);
      heading.textContent = `${d} ${AZ_MONTHS_TITLE[m - 1].toLocaleLowerCase("az")}`;
    } else {
      heading.textContent = "Qarşıdakı xatırlatmalar";
    }
  }
  const clear = document.getElementById("btn-clear-day");
  if (clear) clear.hidden = !state.selected;

  list.innerHTML = "";
  if (!items.length) {
    const p = document.createElement("p");
    p.className = "reminders-empty";
    p.textContent = state.selected
      ? "Bu tarix üçün xatırlatma yoxdur."
      : "Hələ xatırlatma yoxdur. Məsələn deyin: “Sabah saat 10-da dərmanımı xatırlat”.";
    list.append(p);
    return;
  }

  for (const r of items) list.append(reminderCard(r));
}

function reminderCard(r) {
  const card = document.createElement("article");
  card.className = "reminder-item-card samsung-card";
  if (r.id === state.highlightId) card.classList.add("just-added");
  card.setAttribute("aria-label", `${r.title}, ${formatWhen(r.scheduled_at)}`);

  const info = document.createElement("div");
  info.className = "reminder-info";
  const h4 = document.createElement("h4");
  h4.textContent = r.title;
  const p = document.createElement("p");
  p.textContent = formatWhen(r.scheduled_at);
  const badge = document.createElement("span");
  badge.className = "time-badge";
  badge.textContent = relative(r.scheduled_at);
  info.append(h4, p, badge);

  const actions = document.createElement("div");
  actions.className = "reminder-actions";
  actions.append(
    iconButton(ICON_CHECK, `“${r.title}” — edildi kimi qeyd et`, "done", () => markDone(r)),
    iconButton(ICON_TRASH, `“${r.title}” — sil`, "delete", () => remove(r))
  );

  card.append(info, actions);
  return card;
}

const ICON_CHECK = '<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.6" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="20 6 9 17 4 12"/></svg>';
const ICON_TRASH = '<svg width="19" height="19" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></svg>';

function iconButton(svg, label, kind, onClick) {
  const b = document.createElement("button");
  b.type = "button";
  b.className = `reminder-action-btn ${kind}`;
  b.setAttribute("aria-label", label);
  b.title = label;
  b.innerHTML = svg; // static markup only
  b.addEventListener("click", onClick);
  return b;
}

async function markDone(r) {
  haptic("success");
  const previous = r.status;
  r.status = "completed";
  render();
  try {
    await updateReminder(r.id, { status: "completed" });
    toast(`“${r.title}” edildi ✓`, {
      type: "success",
      action: {
        label: "Geri qaytar",
        onClick: async () => {
          r.status = previous;
          render();
          await updateReminder(r.id, { status: previous }).catch(() => {});
          scheduleAlerts(visibleReminders());
        }
      }
    });
  } catch (_) {
    r.status = previous;
    render();
    toast("Yadda saxlanmadı", { type: "error" });
  }
  scheduleAlerts(visibleReminders());
}

function remove(r) {
  haptic("warning");
  // Optimistic delete with a 5-second undo window before the server call
  const timer = setTimeout(async () => {
    pendingDeletes.delete(r.id);
    try {
      await deleteReminder(r.id);
      state.reminders = state.reminders.filter((x) => x.id !== r.id);
    } catch (_) {
      toast("Silinmədi", { type: "error" });
    }
    render();
    scheduleAlerts(visibleReminders());
  }, 5000);
  pendingDeletes.set(r.id, timer);
  render();
  scheduleAlerts(visibleReminders());
  toast(`“${r.title}” silindi`, {
    duration: 5000,
    action: {
      label: "Geri qaytar",
      onClick: () => {
        clearTimeout(pendingDeletes.get(r.id));
        pendingDeletes.delete(r.id);
        render();
        scheduleAlerts(visibleReminders());
      }
    }
  });
}

export function clearDayFilter() {
  state.selected = null;
  render();
}
