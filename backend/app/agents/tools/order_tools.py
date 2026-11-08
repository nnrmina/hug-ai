"""Simulated Wolt food / pharmacy / taxi orders for the demo.

Nothing here places a real order: Wolt has no public ordering API. The backend returns
a structured order preview (vendor, item, price, deep link) that the UI shows for
confirmation and then hands off to Wolt's own search page.
"""
from typing import Any, Dict

ORDER_INTENTS = ("ORDER_FOOD", "ORDER_PHARMACY", "ORDER_TAXI")

_FOOD_CATALOG = {
    "tantuni": {
        "vendor": "Chef Tantuni",
        "item": "Tantuni · 1 pors",
        "price": "8.50 AZN",
        "breakdown": "Yemək 6.50 AZN + Wolt Çatdırılma 2.00 AZN",
        "emoji": "🌯",
        "deep_link": "https://wolt.com/az/aze/baku/search?q=chef+tantuni",
        "confirm_text": "Chef Tantunidən bir pors tantuni sifariş edilsin? Cəmi səkkiz manat əlli qəpik.",
        "done_text": "Chef Tantunidən sifarişiniz qəbul olundu. Kuryer yoldadır.",
    },
    "doner": {
        "vendor": "Wolt Restoran",
        "item": "Dönər · 1 pors",
        "price": "7.00 AZN",
        "breakdown": "Yemək 5.00 AZN + Wolt Çatdırılma 2.00 AZN",
        "emoji": "🥙",
        "deep_link": "https://wolt.com/az/aze/baku/search?q=doner",
        "confirm_text": "Bir pors dönər sifariş edilsin? Cəmi yeddi manat.",
        "done_text": "Dönər sifarişiniz qəbul olundu. Kuryer yoldadır.",
    },
    "bozbas": {
        "vendor": "Wolt Restoran",
        "item": "Bozbaş · Orta pors",
        "price": "12.00 AZN",
        "breakdown": "Yemək 10.00 AZN + Wolt Çatdırılma 2.00 AZN",
        "emoji": "🍲",
        "deep_link": "https://wolt.com/az/aze/baku/search?q=bozbas",
        "confirm_text": "Bir pors bozbaş sifariş edilsin? Cəmi on iki manat.",
        "done_text": "Bozbaş sifarişiniz qəbul olundu. Kuryer yoldadır.",
    },
}

_PHARMACY_ORDER = {
    "vendor": "Zəfəran Aptek",
    "item": "Kardiomaqnil 75 mq",
    "price": "6.20 AZN",
    "breakdown": "Dərman 4.20 AZN + Wolt Çatdırılma 2.00 AZN",
    "emoji": "💊",
    "deep_link": "https://wolt.com/az/aze/baku/search?q=kardiomaqnil",
    "confirm_text": "Aptekdən kardiomaqnil dərmanı sifariş edilsin? Cəmi altı manat iyirmi qəpik.",
    "done_text": "Aptekdən sifarişiniz qəbul olundu. Kuryer yoldadır.",
}

_TAXI_ORDER = {
    "vendor": "Wolt Taxi",
    "item": "Nizami küç. → Şəhər mərkəzi",
    "car": "Toyota Camry · 10-AB-123",
    "driver": "Rəşad M.",
    "price": "5.00 AZN",
    "eta": "3 dəq",
    "emoji": "🚕",
    "confirm_text": "Nizami küçəsindən şəhər mərkəzinə taksi çağırılsın? Qiymət beş manat.",
    "done_text": "Taksi təsdiqləndi. Toyota Camry üç dəqiqəyə çatır.",
}


def _pick_food(text: str) -> Dict[str, Any]:
    lower = text.lower()
    if "dönər" in lower or "doner" in lower:
        return _FOOD_CATALOG["doner"]
    if "bozbaş" in lower or "bozbas" in lower:
        return _FOOD_CATALOG["bozbas"]
    return _FOOD_CATALOG["tantuni"]


def prepare_order(intent: str, text: str) -> Dict[str, Any]:
    """Build a simulated order preview for the given order intent."""
    if intent == "ORDER_PHARMACY":
        order = _PHARMACY_ORDER
    elif intent == "ORDER_TAXI":
        order = _TAXI_ORDER
    else:
        order = _pick_food(text)

    return {
        "action_type": intent,
        "order": dict(order),
        "simulated": True,
        "requires_confirmation": True,
    }
