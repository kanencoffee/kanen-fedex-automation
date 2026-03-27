"""
Shipment CRUD + live tracking refresh.
"""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import get_db
from models import Shipment, ShipmentStatus, TrackingEvent
import fedex_client

router = APIRouter(prefix="/shipments", tags=["shipments"])


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class ShipmentCreate(BaseModel):
    tracking_number: str
    work_order: Optional[str] = None
    customer_name: str
    customer_email: Optional[str] = None
    service_type: Optional[str] = None
    expected_cost: Optional[float] = None
    weight_lb: Optional[float] = None
    origin_city: Optional[str] = None
    destination_city: Optional[str] = None


class ShipmentOut(BaseModel):
    id: str
    tracking_number: str
    work_order: Optional[str]
    customer_name: str
    customer_email: Optional[str]
    service_type: Optional[str]
    status: ShipmentStatus
    expected_cost: Optional[float]
    actual_cost: Optional[float]
    weight_lb: Optional[float]
    origin_city: Optional[str]
    destination_city: Optional[str]
    shipped_at: Optional[datetime]
    estimated_delivery: Optional[datetime]
    delivered_at: Optional[datetime]
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class TrackingEventOut(BaseModel):
    id: str
    timestamp: datetime
    location: Optional[str]
    description: Optional[str]
    event_code: Optional[str]

    class Config:
        from_attributes = True


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/", response_model=ShipmentOut, status_code=201)
async def create_shipment(payload: ShipmentCreate, db: AsyncSession = Depends(get_db)):
    existing = await db.scalar(
        select(Shipment).where(Shipment.tracking_number == payload.tracking_number)
    )
    if existing:
        raise HTTPException(400, "Tracking number already exists.")

    shipment = Shipment(id=str(uuid.uuid4()), **payload.model_dump())
    db.add(shipment)
    await db.commit()
    await db.refresh(shipment)

    # Immediately subscribe to FedEx webhook for real-time push updates
    try:
        from config import get_settings
        settings = get_settings()
        callback = f"{settings.app_base_url}/webhooks/fedex/tracking"
        await fedex_client.subscribe_tracking_webhook(payload.tracking_number, callback)
    except Exception as exc:
        # Non-fatal — polling fallback in scheduler will cover it
        import logging
        logging.getLogger(__name__).warning("Webhook subscription failed: %s", exc)

    return shipment


@router.get("/", response_model=list[ShipmentOut])
async def list_shipments(
    status: Optional[ShipmentStatus] = Query(None),
    work_order: Optional[str] = Query(None),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
):
    q = select(Shipment).order_by(Shipment.created_at.desc()).limit(limit).offset(offset)
    if status:
        q = q.where(Shipment.status == status)
    if work_order:
        q = q.where(Shipment.work_order == work_order)
    result = await db.execute(q)
    return result.scalars().all()


@router.get("/stats")
async def shipment_stats(db: AsyncSession = Depends(get_db)):
    """Dashboard summary counts."""
    rows = await db.execute(
        select(Shipment.status, func.count()).group_by(Shipment.status)
    )
    counts = {row[0]: row[1] for row in rows}
    total = sum(counts.values())
    return {"total": total, "by_status": counts}


@router.get("/{shipment_id}", response_model=ShipmentOut)
async def get_shipment(shipment_id: str, db: AsyncSession = Depends(get_db)):
    s = await db.scalar(
        select(Shipment).where(Shipment.id == shipment_id)
    )
    if not s:
        raise HTTPException(404, "Shipment not found.")
    return s


@router.get("/{shipment_id}/events", response_model=list[TrackingEventOut])
async def get_tracking_events(shipment_id: str, db: AsyncSession = Depends(get_db)):
    s = await db.scalar(
        select(Shipment)
        .where(Shipment.id == shipment_id)
        .options(selectinload(Shipment.events))
    )
    if not s:
        raise HTTPException(404, "Shipment not found.")
    return s.events


@router.post("/{shipment_id}/refresh", response_model=ShipmentOut)
async def refresh_tracking(shipment_id: str, db: AsyncSession = Depends(get_db)):
    """
    Manually trigger a FedEx tracking poll for one shipment.
    The scheduler does this automatically, but useful for on-demand refresh.
    """
    s = await db.scalar(
        select(Shipment)
        .where(Shipment.id == shipment_id)
        .options(selectinload(Shipment.events))
    )
    if not s:
        raise HTTPException(404, "Shipment not found.")

    try:
        raw = await fedex_client.track_shipment(s.tracking_number)
        await _apply_tracking_update(s, raw, db)
        await db.commit()
        await db.refresh(s)
    except Exception as exc:
        raise HTTPException(502, f"FedEx API error: {exc}")

    return s


@router.delete("/{shipment_id}", status_code=204)
async def delete_shipment(shipment_id: str, db: AsyncSession = Depends(get_db)):
    s = await db.scalar(select(Shipment).where(Shipment.id == shipment_id))
    if not s:
        raise HTTPException(404, "Shipment not found.")
    await db.delete(s)
    await db.commit()


# ---------------------------------------------------------------------------
# Shared update logic (used by refresh endpoint + scheduler + webhooks)
# ---------------------------------------------------------------------------

async def _apply_tracking_update(shipment: Shipment, raw: dict, db: AsyncSession):
    """Parse FedEx tracking payload and update DB — idempotent."""
    events = fedex_client.parse_tracking_events(raw)
    est_delivery_str = fedex_client.parse_estimated_delivery(raw)

    if est_delivery_str:
        try:
            dt = datetime.fromisoformat(est_delivery_str.replace("Z", "+00:00"))
            shipment.estimated_delivery = dt.astimezone(timezone.utc).replace(tzinfo=None)
        except ValueError:
            pass

    # Map FedEx event codes to our status enum
    status_map = {
        "OD": ShipmentStatus.OUT_FOR_DELIVERY,
        "DL": ShipmentStatus.DELIVERED,
        "EX": ShipmentStatus.EXCEPTION,
        "PU": ShipmentStatus.IN_TRANSIT,
        "IT": ShipmentStatus.IN_TRANSIT,
    }

    existing_codes = {
        f"{e.event_code}:{e.timestamp.isoformat()}" for e in shipment.events
    }

    for ev in events:
        code = ev.get("event_code")
        ts_str = ev.get("timestamp")
        if not ts_str:
            continue

        try:
            ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            ts = ts.astimezone(timezone.utc).replace(tzinfo=None)
        except ValueError:
            continue

        # Only insert genuinely new events (deduplicate by code+timestamp)
        dedup_key = f"{code}:{ts_str}"
        if dedup_key in existing_codes:
            continue
        existing_codes.add(dedup_key)

        new_event = TrackingEvent(
            id=str(uuid.uuid4()),
            shipment_id=shipment.id,
            timestamp=ts,
            location=ev.get("location"),
            description=ev.get("description"),
            event_code=code,
        )
        db.add(new_event)

        # Update status
        if code in status_map:
            shipment.status = status_map[code]
            if code == "DL":
                shipment.delivered_at = ts
