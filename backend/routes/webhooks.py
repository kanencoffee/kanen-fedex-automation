"""
FedEx tracking webhook receiver.

FedEx POSTs real-time tracking events here when subscribed via
fedex_client.subscribe_tracking_webhook(). This replaces polling for any
shipment that has an active subscription.
"""
import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from models import Shipment
from routes.shipments import _apply_tracking_update

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
logger = logging.getLogger(__name__)


@router.post("/fedex/tracking")
async def fedex_tracking_webhook(request: Request, db: AsyncSession = Depends(get_db)):
    """
    FedEx pushes tracking events here in real time.
    Validate the secret key, then apply the update to the matching shipment.
    """
    from config import get_settings
    secret = request.headers.get("X-FedEx-Webhook-Secret") or ""
    if secret != get_settings().fedex_webhook_secret:
        raise HTTPException(401, "Invalid webhook secret.")

    payload = await request.json()
    logger.info("FedEx webhook received: %s", payload)

    # FedEx webhook body contains the same structure as a tracking API response
    tracking_numbers = _extract_tracking_numbers(payload)

    for tn in tracking_numbers:
        shipment = await db.scalar(
            select(Shipment)
            .where(Shipment.tracking_number == tn)
            .options(selectinload(Shipment.events))
        )
        if not shipment:
            logger.warning("Webhook: no shipment found for tracking number %s", tn)
            continue

        await _apply_tracking_update(shipment, payload, db)

    await db.commit()
    return {"status": "ok"}


def _extract_tracking_numbers(payload: dict) -> list[str]:
    """Pull tracking numbers from a FedEx webhook payload."""
    numbers = []
    try:
        for result in payload.get("output", {}).get("completeTrackResults", []):
            info = result.get("trackResults", [{}])[0]
            tn = info.get("trackingNumberInfo", {}).get("trackingNumber")
            if tn:
                numbers.append(tn)
    except Exception:
        pass
    return numbers
