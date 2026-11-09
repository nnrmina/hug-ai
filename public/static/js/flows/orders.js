// Simulated Wolt order / taxi tracking. Clearly labelled as a demo; the Wolt button opens
// Wolt's real search page for the item.
import { playClip, speak } from "../audio/tts.js";
import { getLang } from "../i18n.js";
import { announce, setText, showScreen } from "../ui/screens.js";

let etaTimer = null;

function countdown(elId, totalSeconds) {
  clearInterval(etaTimer);
  let left = totalSeconds;
  const render = () => {
    const mm = String(Math.floor(left / 60)).padStart(2, "0");
    const ss = String(left % 60).padStart(2, "0");
    setText(elId, `${mm}:${ss}`);
  };
  render();
  etaTimer = setInterval(() => {
    left = Math.max(0, left - 1);
    render();
    if (!left) clearInterval(etaTimer);
  }, 1000);
}

export function stopOrderTimers() {
  clearInterval(etaTimer);
}

export function startOrderTracking(order = {}, spoken = "") {
  setText("order-food-emoji", order.emoji || "🛍️");
  setText("order-card-title", order.item || "");
  setText("order-card-subtitle", order.vendor ? `${order.vendor} (Wolt)` : "Wolt");
  setText("order-card-price", order.price || "");
  setText("order-card-breakdown", order.breakdown || "");
  const wolt = document.getElementById("btn-wolt-deep-link");
  if (wolt && order.deep_link) wolt.href = order.deep_link;
  showScreen("screen-order-tracking");
  countdown("order-eta-countdown", 25 * 60);
  const text = spoken || "Sifarişiniz qəbul olundu. Kuryer yoldadır.";
  announce(text);
  return speak(text, getLang());
}

export function startTaxiTracking(order = {}, spoken = "") {
  if (order.driver) setText("taxi-driver-name", order.driver);
  if (order.car) setText("taxi-driver-car", order.car);
  if (order.eta) setText("taxi-driver-eta", order.eta);
  if (order.item) setText("taxi-route-text", `Götürmə: ${order.item} · ${order.price || ""}`);
  showScreen("screen-taxi-tracking");
  const text = spoken || "Taksi təsdiqləndi.";
  announce(text);
  return speak(text, getLang());
}

export function finishOrder() {
  clearInterval(etaTimer);
  setText("done-message-subtext", "Sifarişiniz təslim edildi. Nuş olsun!");
  showScreen("screen-done");
  playClip("order_done", "Sifarişiniz tamamlandı. Nuş olsun!");
}
