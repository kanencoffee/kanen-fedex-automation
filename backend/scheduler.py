"""
Background scheduler — polling fallback for shipments without active webhooks.

Runs every 4 hours. Only polls shipments that are not yet delivered/returned.
Uses APScheduler with asyncio backend so it shares the FastAPI event loop.
"""
import logging
from datetime import datetime

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from database import AsyncSessionLocal
from models import Shipment, ShipmentStatus
from routes.shipments import _apply_tracking_update
import fedex_client

logger = logging.getLogger(__name__)

ACTIVE_STATUSES = {
    ShipmentStatus.PENDING,
    ShipmentStatus.IN_TRANSIT,
    ShipmentStatus.OUT_FOR_DELIVERY,
}

scheduler = AsyncIOScheduler()


@scheduler.scheduled_job("interval", hours=4, id="poll_tracking")
async def poll_active_shipments():
    """Poll FedEx for all shipments that are still in motion."""
    logger.info("[scheduler] Polling active shipments at %s", datetime.utcnow().isoformat())

    async with AsyncSessionLocal() as db:
        rows = await db.execute(
            select(Shipment)
            .where(Shipment.status.in_(ACTIVE_STATUSES))
            .options(selectinload(Shipment.events))
        )
        shipments = rows.scalars().all()
        logger.info("[scheduler] %d active shipments to poll.", len(shipments))

        for s in shipments:
            try:
                raw = await fedex_client.track_shipment(s.tracking_number)
                await _apply_tracking_update(s, raw, db)
            except Exception as exc:
                logger.error("[scheduler] Failed to update %s: %s", s.tracking_number, exc)

        await db.commit()
        logger.info("[scheduler] Poll complete.")


def start_scheduler():
    scheduler.start()
    logger.info("APScheduler started — polling every 4 hours.")


def stop_scheduler():
    scheduler.shutdown(wait=False)
