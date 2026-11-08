// Non-blocking toasts (replace window.alert). Optional action button, e.g. "Geri qaytar".

export function toast(message, { type = "info", duration = 3200, action } = {}) {
  const host = document.getElementById("toast-host");
  if (!host) return { dismiss() {} };

  const el = document.createElement("div");
  el.className = `toast toast-${type}`;
  el.setAttribute("role", type === "error" ? "alert" : "status");

  const text = document.createElement("span");
  text.className = "toast-text";
  text.textContent = message;
  el.append(text);

  let timer;
  const dismiss = () => {
    clearTimeout(timer);
    el.classList.add("leaving");
    setTimeout(() => el.remove(), 220);
  };

  if (action) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = "toast-action";
    btn.textContent = action.label;
    btn.addEventListener("click", () => {
      action.onClick();
      dismiss();
    });
    el.append(btn);
  }

  host.append(el);
  requestAnimationFrame(() => el.classList.add("shown"));
  timer = setTimeout(dismiss, duration);
  return { dismiss };
}
