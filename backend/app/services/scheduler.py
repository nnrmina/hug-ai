"""Background loop that runs CareService.tick() every SCHEDULER_INTERVAL_S seconds.

Runs inside the single uvicorn worker (see Dockerfile). The tick is idempotent, so a
restart or an overlapping run never double-notifies.
"""
import asyncio

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.logging import logger
from app.services.care_service import CareService


def run_tick_once() -> dict:
    db = SessionLocal()
    try:
        return CareService(db).tick()
    finally:
        db.close()


async def scheduler_loop(stop: asyncio.Event) -> None:
    logger.info("care scheduler started (every %ss)", settings.SCHEDULER_INTERVAL_S)
    while not stop.is_set():
        try:
            stats = await asyncio.to_thread(run_tick_once)
            if any(stats.values()):
                logger.info("care tick: %s", stats)
        except Exception as exc:  # never let the loop die
            logger.exception("care tick failed: %s", exc)
        try:
            await asyncio.wait_for(stop.wait(), timeout=settings.SCHEDULER_INTERVAL_S)
        except asyncio.TimeoutError:
            pass
