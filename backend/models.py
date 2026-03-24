import uuid
import enum
from datetime import datetime

from sqlalchemy import (
    Column, String, DateTime, Float, Text, Enum as SAEnum,
    ForeignKey, Boolean, func,
)
from sqlalchemy.orm import relationship

from database import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class ShipmentStatus(str, enum.Enum):
    PENDING = "pending"
    IN_TRANSIT = "in_transit"
    OUT_FOR_DELIVERY = "out_for_delivery"
    DELIVERED = "delivered"
    EXCEPTION = "exception"
    RETURNED = "returned"


class Shipment(Base):
    __tablename__ = "shipments"

    id = Column(String, primary_key=True, default=_uuid)
    tracking_number = Column(String, unique=True, index=True, nullable=False)

    # Kanen Coffee — ties shipment back to repair job
    work_order = Column(String, index=True, nullable=True)

    customer_name = Column(String, nullable=False)
    customer_email = Column(String, nullable=True)
    service_type = Column(String, nullable=True)          # e.g. "FEDEX_GROUND"
    status = Column(SAEnum(ShipmentStatus), default=ShipmentStatus.PENDING, nullable=False)

    # Costs (expected set at ship time, actual filled from invoice)
    expected_cost = Column(Float, nullable=True)
    actual_cost = Column(Float, nullable=True)
    weight_lb = Column(Float, nullable=True)

    origin_city = Column(String, nullable=True)
    destination_city = Column(String, nullable=True)

    shipped_at = Column(DateTime, nullable=True)
    estimated_delivery = Column(DateTime, nullable=True)
    delivered_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)

    events = relationship(
        "TrackingEvent", back_populates="shipment",
        order_by="TrackingEvent.timestamp.desc()", cascade="all, delete-orphan",
    )
    billing = relationship(
        "BillingRecord", back_populates="shipment",
        uselist=False, cascade="all, delete-orphan",
    )


class TrackingEvent(Base):
    __tablename__ = "tracking_events"

    id = Column(String, primary_key=True, default=_uuid)
    shipment_id = Column(String, ForeignKey("shipments.id", ondelete="CASCADE"), nullable=False)
    timestamp = Column(DateTime, nullable=False)
    location = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    event_code = Column(String, nullable=True)   # FedEx event type code e.g. "OD", "DL"

    shipment = relationship("Shipment", back_populates="events")


class BillingRecord(Base):
    """
    One record per shipment — created when a FedEx invoice is ingested.
    Discrepancies are auto-flagged when |actual - expected| > threshold.
    """
    __tablename__ = "billing_records"

    id = Column(String, primary_key=True, default=_uuid)
    shipment_id = Column(String, ForeignKey("shipments.id", ondelete="CASCADE"), unique=True, nullable=False)
    invoice_number = Column(String, nullable=True)

    expected_cost = Column(Float, nullable=False)
    actual_cost = Column(Float, nullable=False)
    discrepancy = Column(Float, nullable=False)           # actual - expected (negative = overcharged)

    service_type_expected = Column(String, nullable=True)
    service_type_billed = Column(String, nullable=True)

    flagged = Column(Boolean, default=False, nullable=False)
    flag_reason = Column(Text, nullable=True)
    resolved = Column(Boolean, default=False, nullable=False)
    resolved_note = Column(Text, nullable=True)

    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    shipment = relationship("Shipment", back_populates="billing")
