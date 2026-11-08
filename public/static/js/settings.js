// Settings dialog (native <dialog>): AI engine, appearance & accessibility, alerts.
import { ensureAlertPermission, scheduleAlerts } from "./reminders/alerts.js";
import { capabilities, saveSettings, settings } from "./store.js";
import { toast } from "./ui/toast.js";

export function initSettings() {
  const dialog = document.getElementById("settings-dialog");
  const openBtn = document.getElementById("btn-open-settings");
  const form = document.getElementById("settings-form");
  if (!dialog || !openBtn || !form) return;

  const sync = () => {
    // Show what is actually in effect: without server Gemini, browser recognition is used
    // (the saved preference is kept, so it switches back once a key is configured).
    const effective = { ...settings, engine: capabilities.audio_understanding ? settings.engine : "browser" };
    for (const [name, value] of Object.entries(effective)) {
      const inputs = form.elements.namedItem(name);
      if (!inputs) continue;
      if (inputs instanceof RadioNodeList) {
        inputs.forEach((r) => { r.checked = r.value === String(value); });
      } else if (inputs.type === "checkbox") {
        inputs.checked = name === "contrast" ? value === "high" : Boolean(value);
      }
    }
    const status = document.getElementById("engine-status");
    if (status) {
      status.textContent = capabilities.audio_understanding
        ? `Server: Gemini aktivdir (${capabilities.model || "flash"}). Səsiniz Google tərəfindən emal olunur; kontaktlarınız telefonda qalır.`
        : "Server: sadə rejim (Gemini açarı qoşulmayıb). Səs brauzerin öz tanıması ilə işləyir.";
    }
    const geminiRadio = form.querySelector('input[name="engine"][value="auto"]');
    if (geminiRadio) geminiRadio.disabled = !capabilities.audio_understanding;
    const notif = document.getElementById("alerts-status");
    if (notif) {
      const perm = "Notification" in window ? Notification.permission : "unsupported";
      notif.textContent = perm === "granted"
        ? "Bildirişlər açıqdır. Tətbiq açıq və ya quraşdırılmış olduqda xatırladacaq."
        : perm === "denied"
          ? "Bildirişlər brauzerdə bloklanıb — yalnız səsli xatırlatma işləyəcək."
          : "Tətbiq açıq olduqda səsli xatırladacaq. Bildiriş üçün icazə istəniləcək.";
    }
  };

  openBtn.addEventListener("click", () => {
    sync();
    dialog.showModal();
  });

  form.addEventListener("change", async (e) => {
    const { name, type, value, checked } = e.target;
    if (!name) return;
    if (name === "contrast") saveSettings({ contrast: checked ? "high" : "normal" });
    else if (type === "checkbox") saveSettings({ [name]: checked });
    else saveSettings({ [name]: value });

    if (name === "alerts") {
      if (checked) await ensureAlertPermission();
      scheduleAlerts();
    }
    sync();
  });

  document.getElementById("btn-close-settings")?.addEventListener("click", () => dialog.close());
  dialog.addEventListener("click", (e) => {
    if (e.target === dialog) dialog.close(); // click on backdrop
  });
  dialog.addEventListener("close", () => toast("Tənzimləmələr yadda saxlanıldı", { duration: 1800 }));
}
