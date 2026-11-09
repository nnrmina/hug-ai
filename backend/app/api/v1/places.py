from fastapi import APIRouter, Query

from app.services import places_service

router = APIRouter()


@router.get("/places/nearby")
def nearby_places(
    lat: float = Query(..., ge=-90, le=90),
    lon: float = Query(..., ge=-180, le=180),
    type: str = Query(default="pharmacy", pattern="^(pharmacy|hospital)$"),
):
    """Nearest pharmacies / hospitals from OpenStreetMap, closest first."""
    return {"type": type, "places": places_service.nearby(lat, lon, type, limit=3)}
