"""
Billing audit system — ingest FedEx invoices, auto-flag discrepancies.
"""
import csv
import io
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from config import get_settings
from database import get_db
from models import BillingRecord, Shipment

router = APIRouter(prefix="/billing", tags=["billing"])
settings = get_settings()


# ---------------------------------------------------------------------------
# Schemas
# ---------------------------------------------------------------------------

class InvoiceIngest(BaseModel):
    """
    POST this for each line on a FedEx invoice.
    The tracking number links it back to the shipment's expected_cost.
    """
    tracking_number: str
    invoice_number: Optional[str] = None
    actual_cost: float
    service_type_billed: Optional[str] = None


class BillingRecordOut(BaseModel):
    id: str
    shipment_id: str
    invoice_number: Optional[str]
    expected_cost: float
    actual_cost: float
    discrepancy: float
    service_type_expected: Optional[str]
    service_type_billed: Optional[str]
    flagged: bool
    flag_reason: Optional[str]
    resolved: bool
    resolved_note: Optional[str]

    # Denormalized for convenience in the frontend
    tracking_number: Optional[str] = None
    work_order: Optional[str] = None
    customer_name: Optional[str] = None

    class Config:
        from_attributes = True


class ResolvePayload(BaseModel):
    resolved_note: Optional[str] = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/ingest", response_model=BillingRecordOut, status_code=201)
async def ingest_invoice_line(payload: InvoiceIngest, db: AsyncSession = Depends(get_db)):
    """
    Accepts one invoice line item. Automatically:
    - Looks up the matching shipment by tracking number
    - Computes discrepancy = actual - expected
    - Flags if |discrepancy| > threshold or service types mismatch
    """
    shipment = await db.scalar(
        select(Shipment).where(Shipment.tracking_number == payload.tracking_number)
    )
    if not shipment:
        raise HTTPException(404, f"No shipment found for tracking number {payload.tracking_number!r}.")

    existing = await db.scalar(
        select(BillingRecord).where(BillingRecord.shipment_id == shipment.id)
    )
    if existing:
        raise HTTPException(400, "Billing record already exists for this shipment. Use PATCH to update.")

    expected = shipment.expected_cost or 0.0
    actual = payload.actual_cost
    discrepancy = actual - expected  # positive = we were charged more than expected

    flag_reasons = []
    if abs(discrepancy) > settings.billing_alert_threshold:
        flag_reasons.append(f"Cost discrepancy ${discrepancy:+.2f} exceeds threshold ${settings.billing_alert_threshold:.2f}")
    if (
        payload.service_type_billed
        and shipment.service_type
        and payload.service_type_billed != shipment.service_type
    ):
        flag_reasons.append(
            f"Service type mismatch: expected {shipment.service_type!r}, billed {payload.service_type_billed!r}"
        )

    record = BillingRecord(
        id=str(uuid.uuid4()),
        shipment_id=shipment.id,
        invoice_number=payload.invoice_number,
        expected_cost=expected,
        actual_cost=actual,
        discrepancy=discrepancy,
        service_type_expected=shipment.service_type,
        service_type_billed=payload.service_type_billed,
        flagged=bool(flag_reasons),
        flag_reason="; ".join(flag_reasons) if flag_reasons else None,
    )

    # Keep shipment actual cost in sync
    shipment.actual_cost = actual

    db.add(record)
    await db.commit()
    await db.refresh(record)

    return _enrich(record, shipment)


@router.get("/", response_model=list[BillingRecordOut])
async def list_billing(
    flagged_only: bool = Query(False),
    resolved: bool = Query(False),
    limit: int = Query(50, le=200),
    offset: int = Query(0),
    db: AsyncSession = Depends(get_db),
):
    q = (
        select(BillingRecord)
        .options(selectinload(BillingRecord.shipment))
        .order_by(BillingRecord.created_at.desc())
        .limit(limit)
        .offset(offset)
    )
    if flagged_only:
        q = q.where(BillingRecord.flagged == True)
    if not resolved:
        q = q.where(BillingRecord.resolved == False)

    rows = await db.execute(q)
    records = rows.scalars().all()
    return [_enrich(r, r.shipment) for r in records]


@router.get("/summary")
async def billing_summary(db: AsyncSession = Depends(get_db)):
    """Aggregate stats for the billing dashboard card."""
    rows = await db.execute(select(BillingRecord))
    all_records = rows.scalars().all()

    total = len(all_records)
    flagged = sum(1 for r in all_records if r.flagged and not r.resolved)
    total_discrepancy = sum(r.discrepancy for r in all_records)
    overcharged = sum(r.discrepancy for r in all_records if r.discrepancy > 0)

    return {
        "total_invoices": total,
        "flagged_unresolved": flagged,
        "total_discrepancy_usd": round(total_discrepancy, 2),
        "total_overcharged_usd": round(overcharged, 2),
    }


@router.patch("/{record_id}/resolve", response_model=BillingRecordOut)
async def resolve_billing(
    record_id: str, payload: ResolvePayload, db: AsyncSession = Depends(get_db)
):
    record = await db.scalar(
        select(BillingRecord)
        .where(BillingRecord.id == record_id)
        .options(selectinload(BillingRecord.shipment))
    )
    if not record:
        raise HTTPException(404, "Billing record not found.")

    record.resolved = True
    record.resolved_note = payload.resolved_note
    await db.commit()
    await db.refresh(record)
    return _enrich(record, record.shipment)


@router.get("/export/csv")
async def export_csv(
    flagged_only: bool = Query(False),
    db: AsyncSession = Depends(get_db),
):
    """Download all billing records as a CSV — useful for accountant review."""
    q = select(BillingRecord).options(selectinload(BillingRecord.shipment))
    if flagged_only:
        q = q.where(BillingRecord.flagged == True)
    rows = (await db.execute(q)).scalars().all()

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Invoice #", "Tracking #", "Work Order", "Customer",
        "Expected ($)", "Actual ($)", "Discrepancy ($)",
        "Service Expected", "Service Billed",
        "Flagged", "Flag Reason", "Resolved",
    ])
    for r in rows:
        s = r.shipment
        writer.writerow([
            r.invoice_number or "",
            s.tracking_number if s else "",
            s.work_order or "" if s else "",
            s.customer_name if s else "",
            f"{r.expected_cost:.2f}",
            f"{r.actual_cost:.2f}",
            f"{r.discrepancy:+.2f}",
            r.service_type_expected or "",
            r.service_type_billed or "",
            "Yes" if r.flagged else "No",
            r.flag_reason or "",
            "Yes" if r.resolved else "No",
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.read()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=kanen-billing-audit.csv"},
    )


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _enrich(record: BillingRecord, shipment: Shipment | None) -> dict:
    data = BillingRecordOut.model_validate(record).model_dump()
    if shipment:
        data["tracking_number"] = shipment.tracking_number
        data["work_order"] = shipment.work_order
        data["customer_name"] = shipment.customer_name
    return data
