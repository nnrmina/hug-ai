// Screen navigation with View Transitions (where supported), focus management and
// screen-reader announcements.

const reduceMotion = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
let currentId = "screen-home";
const listeners = new Set();

export const currentScreen = () => currentId;
export const onScreenChange = (fn) => listeners.add(fn);

function swap(id) {
  document.querySelectorAll(".screen-view").forEach((s) => {
    const active = s.id === id;
    s.classList.toggle("active", active);
    s.toggleAttribute("inert", !active);
    s.setAttribute("aria-hidden", active ? "false" : "true");
  });
}

export function showScreen(id, { focus = true } = {}) {
  const target = document.getElementById(id);
  if (!target) return;
  const previous = currentId;
  currentId = id;

  if (previous !== id && document.startViewTransition && !reduceMotion() && document.visibilityState === "visible") {
    const transition = document.startViewTransition(() => swap(id));
    transition.ready?.catch(() => {});
    transition.finished?.catch(() => {});
  } else {
    swap(id);
  }

  if (focus && previous !== id) {
    // Move focus to the screen's heading so keyboard / screen-reader users land in context
    requestAnimationFrame(() => {
      const heading = target.querySelector("[data-screen-title]") || target.querySelector("h1, h2");
      if (heading) {
        heading.setAttribute("tabindex", "-1");
        heading.focus({ preventScroll: true });
      }
    });
  }
  listeners.forEach((fn) => fn(id, previous));
}

// Polite live region: everything the assistant says is also announced to screen readers
export function announce(text) {
  const region = document.getElementById("sr-live");
  if (!region || !text) return;
  region.textContent = "";
  setTimeout(() => { region.textContent = text; }, 50);
}

export function setText(id, value) {
  const el = document.getElementById(id);
  if (el) el.textContent = value ?? "";
  return el;
}
