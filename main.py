"""
SkySync 2.0 — FastAPI backend
Run:  uvicorn main:app --reload --host 127.0.0.1 --port 8000
"""

import os
from datetime import datetime
from typing import List, Optional

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, HTTPException, Depends, BackgroundTasks
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi.staticfiles import StaticFiles
from starlette.requests import Request
from sqlalchemy.orm import Session
from pydantic import BaseModel

from database import engine, get_db, Base
from models import Tracker, PriceSnapshot
from analytics import get_buy_signal
from scheduler import start_scheduler, stop_scheduler, schedule_tracker, unschedule_tracker, trigger_scan_async

# Create DB tables on startup
Base.metadata.create_all(bind=engine)

app = FastAPI(title="SkySync", version="2.0.0")
templates = Jinja2Templates(directory="templates")


# ── Lifecycle ─────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def on_startup():
    start_scheduler()


@app.on_event("shutdown")
async def on_shutdown():
    stop_scheduler()


# ── Frontend ──────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def dashboard(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class TrackerCreate(BaseModel):
    name: str
    origin: str          # IATA e.g. "TLV"
    destination: str     # IATA e.g. "NRT"
    duration_min: int = 7
    duration_max: int = 14
    window_start: str    # "YYYY-MM-DD"
    window_end: str      # "YYYY-MM-DD"
    target_price: Optional[float] = None
    scan_interval_hours: int = 6
    baggage_required: bool = False
    alert_email: Optional[str] = None
    currency: str = "USD"


class TrackerOut(BaseModel):
    id: int
    name: str
    origin: str
    destination: str
    duration_min: int
    duration_max: int
    window_start: str
    window_end: str
    target_price: Optional[float]
    scan_interval_hours: int
    baggage_required: bool
    alert_email: Optional[str]
    active: bool
    created_at: datetime
    last_scanned: Optional[datetime]
    current_best_price: Optional[float]
    previous_best_price: Optional[float]
    currency: str

    class Config:
        from_attributes = True


# ── Tracker CRUD ──────────────────────────────────────────────────────────────

@app.get("/api/trackers", response_model=List[TrackerOut])
def list_trackers(db: Session = Depends(get_db)):
    return (
        db.query(Tracker)
        .filter(Tracker.active == True)
        .order_by(Tracker.created_at.desc())
        .all()
    )


@app.post("/api/trackers", response_model=TrackerOut, status_code=201)
def create_tracker(data: TrackerCreate, db: Session = Depends(get_db)):
    tracker = Tracker(**data.model_dump())
    db.add(tracker)
    db.commit()
    db.refresh(tracker)
    # Schedule periodic scans
    schedule_tracker(tracker.id, tracker.scan_interval_hours)
    # Immediate first scan
    trigger_scan_async(tracker.id)
    return tracker


@app.delete("/api/trackers/{tracker_id}", status_code=204)
def delete_tracker(tracker_id: int, db: Session = Depends(get_db)):
    tracker = db.query(Tracker).filter(Tracker.id == tracker_id).first()
    if not tracker:
        raise HTTPException(404, "Tracker not found")
    tracker.active = False
    unschedule_tracker(tracker_id)
    db.commit()


@app.patch("/api/trackers/{tracker_id}", response_model=TrackerOut)
def update_tracker(tracker_id: int, data: TrackerCreate, db: Session = Depends(get_db)):
    tracker = db.query(Tracker).filter(Tracker.id == tracker_id, Tracker.active == True).first()
    if not tracker:
        raise HTTPException(404, "Tracker not found")
    for k, v in data.model_dump().items():
        setattr(tracker, k, v)
    db.commit()
    db.refresh(tracker)
    schedule_tracker(tracker.id, tracker.scan_interval_hours)
    return tracker


# ── Scan control ──────────────────────────────────────────────────────────────

@app.post("/api/trackers/{tracker_id}/scan")
def manual_scan(tracker_id: int, db: Session = Depends(get_db)):
    tracker = db.query(Tracker).filter(Tracker.id == tracker_id, Tracker.active == True).first()
    if not tracker:
        raise HTTPException(404, "Tracker not found")
    trigger_scan_async(tracker_id)
    return {"status": "scanning", "tracker_id": tracker_id}


# ── History & analytics ───────────────────────────────────────────────────────

@app.get("/api/trackers/{tracker_id}/history")
def get_history(tracker_id: int, db: Session = Depends(get_db)):
    tracker = db.query(Tracker).filter(Tracker.id == tracker_id).first()
    if not tracker:
        raise HTTPException(404, "Tracker not found")

    snaps = (
        db.query(PriceSnapshot)
        .filter(PriceSnapshot.tracker_id == tracker_id)
        .order_by(PriceSnapshot.scanned_at.asc())
        .all()
    )

    history = [
        {
            "id": s.id,
            "timestamp": s.scanned_at.isoformat(),
            "total_price": s.total_price,
            "outbound_price": s.outbound_price,
            "return_price": s.return_price,
            "outbound_date": s.outbound_date,
            "return_date": s.return_date,
            "source": s.source,
            "booking_url": s.booking_url,
            "baggage_included": s.baggage_included,
            "fare_class": s.fare_class,
            "currency": s.currency or tracker.currency,
        }
        for s in snaps
    ]

    prices = [s.total_price for s in snaps]
    signal = get_buy_signal(prices)

    return {"history": history, "signal": signal, "tracker": TrackerOut.model_validate(tracker).model_dump()}


@app.get("/api/stats")
def get_stats(db: Session = Depends(get_db)):
    """Dashboard-level aggregate stats."""
    active_count = db.query(Tracker).filter(Tracker.active == True).count()
    snap_count = db.query(PriceSnapshot).count()

    # Trackers that are below target
    alerts_triggered = 0
    trackers = db.query(Tracker).filter(Tracker.active == True, Tracker.target_price != None).all()
    for t in trackers:
        if t.current_best_price and t.current_best_price <= t.target_price:
            alerts_triggered += 1

    return {
        "active_trackers": active_count,
        "total_scans": snap_count,
        "alerts_triggered": alerts_triggered,
    }
