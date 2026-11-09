"""Live weather via Open-Meteo (free, no API key), phrased for speaking aloud in AZ / RU."""
import time
from typing import Any, Dict, Optional, Tuple

import httpx

from app.core.logging import logger

BAKU = (40.4093, 49.8671)
URL = "https://api.open-meteo.com/v1/forecast"
TIMEOUT_S = 6.0
CACHE_TTL_S = 600
_cache: Dict[Tuple[float, float], Tuple[float, Dict[str, Any]]] = {}

# WMO weather codes -> (az now, az forecast noun, ru)
_WMO = [
    ((0,), ("hava açıq və günəşlidir", "açıq, günəşli hava", "ясно, солнечно")),
    ((1, 2), ("hava az buludludur", "az buludlu hava", "переменная облачность")),
    ((3,), ("hava buludludur", "buludlu hava", "облачно")),
    ((45, 48), ("hava dumanlıdır", "duman", "туман")),
    ((51, 53, 55, 56, 57), ("çiskin yağış yağır", "çiskin yağış", "морось")),
    ((61, 63, 80, 81), ("yağış yağır", "yağış", "дождь")),
    ((65, 82), ("güclü yağış yağır", "güclü yağış", "сильный дождь")),
    ((66, 67), ("buzlu yağış yağır", "buzlu yağış", "ледяной дождь")),
    ((71, 73, 75, 77, 85, 86), ("qar yağır", "qar", "снег")),
    ((95, 96, 99), ("ildırımlı yağış yağır", "ildırımlı yağış", "гроза")),
]


def describe(code: Optional[int], lang: str, forecast: bool = False) -> str:
    for codes, words in _WMO:
        if code in codes:
            return words[2] if lang == "ru" else words[1] if forecast else words[0]
    if code is None:
        return ""
    return "переменная погода" if lang == "ru" else "dəyişkən hava" if forecast else "hava dəyişkəndir"


def _deg(v: float) -> str:
    n = round(v)
    return f"+{n}" if n > 0 else str(n)


def fetch(lat: float, lon: float, client: Optional[httpx.Client] = None) -> Dict[str, Any]:
    key = (round(lat, 2), round(lon, 2))
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < CACHE_TTL_S:
        return hit[1]
    params = {
        "latitude": key[0], "longitude": key[1], "timezone": "Asia/Baku", "forecast_days": 2,
        "current": "temperature_2m,weather_code,wind_speed_10m",
        "daily": "temperature_2m_max,temperature_2m_min,precipitation_probability_max,weather_code",
    }
    if client is not None:
        r = client.get(URL, params=params, timeout=TIMEOUT_S)
    else:
        r = httpx.get(URL, params=params, timeout=TIMEOUT_S)
    r.raise_for_status()
    data = r.json()
    _cache[key] = (time.time(), data)
    return data


def weather_reply(lat: Optional[float], lon: Optional[float], day: str = "today", lang: str = "az",
                  client: Optional[httpx.Client] = None) -> Tuple[str, Optional[Dict[str, Any]]]:
    """Return (spoken text, compact data for the UI)."""
    here = lat is not None and lon is not None
    lat, lon = (lat, lon) if here else BAKU
    try:
        data = fetch(lat, lon, client)
        cur = data.get("current") or {}
        daily = data.get("daily") or {}
        i = 1 if day == "tomorrow" else 0
        tmax = daily["temperature_2m_max"][i]
        tmin = daily["temperature_2m_min"][i]
        rain = (daily.get("precipitation_probability_max") or [None, None])[i]
        dcode = daily["weather_code"][i]
    except Exception as exc:  # network, timeout, bad payload
        logger.warning("weather unavailable: %s", exc)
        return (("Не получилось узнать погоду. Попробуйте чуть позже." if lang == "ru"
                 else "Hazırda hava məlumatını ala bilmədim. Bir az sonra yenidən soruşun."), None)

    place_az, place_ru = ("Olduğunuz yerdə", "У Вас") if here else ("Bakıda", "В Баку")
    rain_txt = ""
    if rain is not None and rain >= 30:
        rain_txt = (f" Вероятность дождя {round(rain)}%." if lang == "ru"
                    else f" Yağış ehtimalı {round(rain)} faizdir.")
    if day == "tomorrow":
        if lang == "ru":
            text = (f"Завтра {'у Вас' if here else 'в Баку'}: {describe(dcode, lang)}, "
                    f"от {_deg(tmin)} до {_deg(tmax)} градусов.{rain_txt}")
        else:
            text = (f"Sabah {'olduğunuz yerdə' if here else 'Bakıda'} {describe(dcode, lang, True)} gözlənilir, "
                    f"{_deg(tmin)} ilə {_deg(tmax)} dərəcə arası.{rain_txt}")
        feel = tmax
    else:
        now_t = cur.get("temperature_2m")
        ccode = cur.get("weather_code", dcode)
        if lang == "ru":
            text = (f"{place_ru} сейчас {_deg(now_t)} градусов, {describe(ccode, lang)}. "
                    f"Днём до {_deg(tmax)}, ночью до {_deg(tmin)}.{rain_txt}")
        else:
            text = (f"{place_az} indi {_deg(now_t)} dərəcədir, {describe(ccode, lang)}. "
                    f"Gün ərzində {_deg(tmin)} ilə {_deg(tmax)} dərəcə arası.{rain_txt}")
        feel = now_t if now_t is not None else tmax
    if feel is not None and feel <= 3:
        text += " Одевайтесь теплее." if lang == "ru" else " İsti geyinin."
    elif tmax is not None and tmax >= 33:
        text += " Жарко — пейте больше воды." if lang == "ru" else " İstidir, çox su için."
    ui = {"day": day, "min": tmin, "max": tmax, "rain": rain, "code": dcode,
          "now": cur.get("temperature_2m"), "here": here}
    return text, ui
