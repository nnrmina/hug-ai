"""Nearest pharmacies / hospitals from OpenStreetMap (free, no key).

Primary source is Nominatim's category search inside a bounding box (fast and reliable);
the public Overpass API is a fallback because it is often overloaded."""
import math
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx

from app.core.logging import logger

OVERPASS_URLS = ["https://overpass-api.de/api/interpreter"]
NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
HEADERS = {"User-Agent": "HUG-assistant/1.0 (elderly voice assistant; hug.46-224-126-66.sslip.io)"}
TIMEOUT_S = 6.0
CACHE_TTL_S = 600
AMENITIES = {"pharmacy": "pharmacy", "hospital": "hospital|clinic|doctors"}
_cache: Dict[Tuple[str, float, float], Tuple[float, List[Dict[str, Any]]]] = {}


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _query(kind: str, lat: float, lon: float, radius: int) -> str:
    amen = AMENITIES.get(kind, "pharmacy")
    return (f'[out:json][timeout:7];(nwr["amenity"~"^({amen})$"](around:{radius},{lat},{lon}););'
            f"out center tags 40;")


def parse_elements(elements: List[Dict[str, Any]], lat: float, lon: float, kind: str) -> List[Dict[str, Any]]:
    out = []
    for el in elements:
        tags = el.get("tags") or {}
        plat = el.get("lat") or (el.get("center") or {}).get("lat")
        plon = el.get("lon") or (el.get("center") or {}).get("lon")
        if plat is None or plon is None:
            continue
        name = tags.get("name:az") or tags.get("name") or tags.get("brand") or (
            "Aptek" if kind == "pharmacy" else "Tibb müəssisəsi")
        out.append({
            "name": name,
            "lat": plat,
            "lon": plon,
            "distance_m": round(haversine_m(lat, lon, plat, plon)),
            "phone": tags.get("phone") or tags.get("contact:phone"),
            "opening_hours": tags.get("opening_hours"),
            "address": " ".join(filter(None, [tags.get("addr:street"), tags.get("addr:housenumber")])) or None,
        })
    out.sort(key=lambda p: p["distance_m"])
    # Same chain often appears twice (node + building): keep the closest of each name+distance bucket
    seen, uniq = set(), []
    for p in out:
        k = (p["name"], p["distance_m"] // 40)
        if k not in seen:
            seen.add(k)
            uniq.append(p)
    return uniq


def _bbox(lat: float, lon: float, radius_m: int) -> str:
    dlat = radius_m / 111_000
    dlon = radius_m / (111_000 * max(0.2, math.cos(math.radians(lat))))
    return f"{lon - dlon:.5f},{lat + dlat:.5f},{lon + dlon:.5f},{lat - dlat:.5f}"


def _nominatim(kind: str, lat: float, lon: float, radius: int, client) -> List[Dict[str, Any]]:
    params = {"q": "pharmacy" if kind == "pharmacy" else "hospital", "format": "jsonv2", "bounded": 1,
              "viewbox": _bbox(lat, lon, radius), "limit": 40, "extratags": 1, "addressdetails": 1}
    r = (client or httpx).get(NOMINATIM_URL, params=params, headers=HEADERS, timeout=TIMEOUT_S)
    r.raise_for_status()
    elements = []
    for x in r.json():
        if x.get("category") != "amenity":
            continue
        tags = dict(x.get("extratags") or {})
        addr = x.get("address") or {}
        tags.setdefault("name", x.get("name") or "")
        tags.setdefault("addr:street", addr.get("road"))
        tags.setdefault("addr:housenumber", addr.get("house_number"))
        elements.append({"lat": float(x["lat"]), "lon": float(x["lon"]),
                         "tags": {k: v for k, v in tags.items() if v}})
    return parse_elements(elements, lat, lon, kind)


def _overpass(kind: str, lat: float, lon: float, radius: int, client) -> List[Dict[str, Any]]:
    q = _query(kind, lat, lon, radius)
    r = (client or httpx).post(OVERPASS_URLS[0], data={"data": q}, headers=HEADERS, timeout=TIMEOUT_S)
    r.raise_for_status()
    return parse_elements(r.json().get("elements") or [], lat, lon, kind)


def nearby(lat: float, lon: float, kind: str = "pharmacy", limit: int = 3,
           client: Optional[httpx.Client] = None) -> List[Dict[str, Any]]:
    kind = kind if kind in AMENITIES else "pharmacy"
    key = (kind, round(lat, 3), round(lon, 3))
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < CACHE_TTL_S:
        return hit[1][:limit]
    places: List[Dict[str, Any]] = []
    for radius in (1500, 5000):
        for source in (_nominatim, _overpass):
            try:
                places = source(kind, lat, lon, radius, client)
            except Exception as exc:
                logger.warning("places via %s failed: %s", source.__name__, exc)
                continue
            if places:
                break
        if places:
            break
    if places:  # never cache a failure / empty answer
        _cache[key] = (time.time(), places)
    return places[:limit]
