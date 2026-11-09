// "Ən yaxın aptek hardadır?": find the nearest pharmacies / hospitals on OpenStreetMap,
// show them on a map with directions and a call button.
import { nearbyPlaces } from "../api.js";
import { speak } from "../audio/tts.js";
import { getLang } from "../i18n.js";
import { BAKU, getLocation, knownLocation } from "../location.js";
import { isNativeApp } from "../native.js";
import { announce, setText, showScreen } from "../ui/screens.js";
import { toast } from "../ui/toast.js";

const say = (text) => { announce(text); return speak(text, getLang()); };

function fmtDistance(m, ru) {
  if (m < 1000) return `${Math.max(10, Math.round(m / 10) * 10)} ${ru ? "м" : "metr"}`;
  return `${(m / 1000).toFixed(1).replace(".", ",")} ${ru ? "км" : "km"}`;
}

function mapUrl(center, target) {
  const pts = [center, target].filter(Boolean);
  const lats = pts.map((p) => p.lat), lons = pts.map((p) => p.lon);
  const pad = 0.004;
  const bbox = [Math.min(...lons) - pad, Math.min(...lats) - pad, Math.max(...lons) + pad, Math.max(...lats) + pad]
    .map((v) => v.toFixed(5)).join(",");
  const marker = target || center;
  return `https://www.openstreetmap.org/export/embed.html?bbox=${bbox}&layer=mapnik&marker=${marker.lat.toFixed(5)},${marker.lon.toFixed(5)}`;
}

const directionsUrl = (p) => `https://www.google.com/maps/dir/?api=1&destination=${p.lat},${p.lon}&travelmode=walking`;

function renderList(places, ru, hospital) {
  const list = document.getElementById("places-list");
  list.innerHTML = "";
  places.forEach((p, i) => {
    const card = document.createElement("div");
    card.className = `samsung-card place-card${i === 0 ? " nearest" : ""}`;
    card.innerHTML = `<div class="place-info"><h4></h4><p></p></div><div class="place-actions"></div>`;
    card.querySelector("h4").textContent = p.name;
    const meta = [fmtDistance(p.distance_m, ru), p.address, p.opening_hours === "24/7" ? (ru ? "круглосуточно" : "24 saat") : null]
      .filter(Boolean).join(" · ");
    card.querySelector("p").textContent = meta;
    const actions = card.querySelector(".place-actions");
    const go = document.createElement("a");
    go.className = "place-btn primary";
    go.href = directionsUrl(p);
    go.target = isNativeApp() ? "_self" : "_blank";
    go.rel = "noopener";
    go.textContent = ru ? "Маршрут" : "Yol göstər";
    actions.append(go);
    if (p.phone) {
      const call = document.createElement("a");
      call.className = "place-btn";
      call.href = `tel:${p.phone.split(/[;,]/)[0].replace(/[^\d+]/g, "")}`;
      call.setAttribute("aria-label", `${p.name} — ${ru ? "позвонить" : "zəng et"}`);
      call.textContent = "📞";
      actions.append(call);
    }
    card.addEventListener("click", (e) => {
      if (e.target.closest("a")) return;
      document.getElementById("places-map").src = mapUrl(null, p);
    });
    list.append(card);
  });
  if (!places.length) {
    list.innerHTML = `<p class="reminders-empty">${ru ? "Поблизости ничего не нашлось." : hospital ? "Yaxınlıqda xəstəxana tapılmadı." : "Yaxınlıqda aptek tapılmadı."}</p>`;
  }
}

export async function openPlaces(type = "pharmacy", { spoken = "" } = {}) {
  const ru = getLang() === "ru";
  const hospital = type === "hospital";
  setText("places-title", ru ? (hospital ? "Больницы рядом" : "Аптеки рядом") : (hospital ? "Yaxın xəstəxanalar" : "Yaxın apteklər"));
  setText("places-status", ru ? "Определяю Ваше местоположение…" : "Yerinizi müəyyən edirəm…");
  document.getElementById("places-list").innerHTML = "";
  const frame = document.getElementById("places-map");
  frame.removeAttribute("src");
  showScreen("screen-places");
  if (spoken) say(spoken);

  let loc = knownLocation() || (await getLocation());
  let approx = false;
  if (!loc) {
    loc = BAKU;
    approx = true;
    toast(ru ? "Нет доступа к местоположению — показываю центр Баку" : "Yerinizə icazə yoxdur — Bakı mərkəzi göstərilir");
  }
  setText("places-status", ru ? "Ищу поблизости…" : "Yaxınlıqda axtarıram…");

  let places = [];
  try {
    places = (await nearbyPlaces(loc.lat, loc.lon, type)).places || [];
  } catch (err) {
    setText("places-status", ru ? "Не получилось загрузить карту." : "Xəritə yüklənmədi. İnterneti yoxlayın.");
    say(ru ? "Сейчас не получилось найти. Попробуйте чуть позже." : "Hazırda tapa bilmədim. Bir az sonra yenidən cəhd edin.");
    return;
  }
  frame.src = mapUrl(loc, places[0]);
  setText("places-status", approx ? (ru ? "Примерно: центр Баку" : "Təxmini: Bakı mərkəzi") : (ru ? "Рядом с Вами" : "Sizə ən yaxın"));
  renderList(places, ru, hospital);

  if (places.length) {
    const p = places[0];
    say(ru
      ? `Ближайшая ${hospital ? "больница" : "аптека"}: ${p.name}, ${fmtDistance(p.distance_m, true)}. Показываю на карте.`
      : `Ən yaxın ${hospital ? "tibb müəssisəsi" : "aptek"}: ${p.name}, ${fmtDistance(p.distance_m, false)} məsafədə. Xəritədə göstərirəm.`);
  } else {
    say(ru ? "Поблизости ничего не нашлось." : "Yaxınlıqda heç nə tapa bilmədim.");
  }
}
