from sqlalchemy import Column, Integer, String, Float, DateTime, Boolean, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from database import Base


class Tracker(Base):
    __tablename__ = "trackers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    origin = Column(String(3), nullable=False)       # IATA code e.g. "TLV"
    destination = Column(String(3), nullable=False)  # IATA code e.g. "NRT"
    duration_min = Column(Integer, nullable=False, default=7)
    duration_max = Column(Integer, nullable=False, default=14)
    window_start = Column(String, nullable=False)    # ISO date string "2025-10-01"
    window_end = Column(String, nullable=False)      # ISO date string "2025-11-30"
    target_price = Column(Float, nullable=True)
    scan_interval_hours = Column(Integer, default=6)
    baggage_required = Column(Boolean, default=False)
    alert_email = Column(String, nullable=True)
    active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_scanned = Column(DateTime, nullable=True)
    current_best_price = Column(Float, nullable=True)
    previous_best_price = Column(Float, nullable=True)
    currency = Column(String, default="USD")

    snapshots = relationship(
        "PriceSnapshot", back_populates="tracker", cascade="all, delete-orphan"
    )


class PriceSnapshot(Base):
    __tablename__ = "price_snapshots"

    id = Column(Integer, primary_key=True, index=True)
    tracker_id = Column(Integer, ForeignKey("trackers.id"), nullable=False)
    scanned_at = Column(DateTime, default=datetime.utcnow)
    outbound_price = Column(Float, nullable=True)
    return_price = Column(Float, nullable=True)
    total_price = Column(Float, nullable=False)
    outbound_date = Column(String, nullable=True)
    return_date = Column(String, nullable=True)
    source = Column(String, default="amadeus")
    booking_url = Column(Text, nullable=True)
    baggage_included = Column(Boolean, default=False)
    fare_class = Column(String, nullable=True)
    is_split_ticket = Column(Boolean, default=False)
    currency = Column(String, default="USD")

    tracker = relationship("Tracker", back_populates="snapshots")
