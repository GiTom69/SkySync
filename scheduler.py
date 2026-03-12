"""
Background scheduler for periodic tracker scans.
Uses APScheduler running in the same process as FastAPI.
"""

import threading
from datetime import datetime
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

_scheduler = BackgroundScheduler(timezone="UTC")
_tracker_scan_locks = {}
_tracker_scan_locks_guard = threading.Lock()


def _get_tracker_lock(tracker_id: int) -> threading.Lock:
    with _tracker_scan_locks_guard:
        lock = _tracker_scan_locks.get(tracker_id)
        if lock is None:
            lock = threading.Lock()
            _tracker_scan_locks[tracker_id] = lock
        return lock


def scan_tracker(tracker_id: int, trigger_source: str = "scheduled") -> None:
    """Scan one tracker: call Amadeus, persist snapshot, fire alerts if needed."""
    from database import SessionLocal
    from models import Tracker, PriceSnapshot
    from amadeus_client import scan_window
    from notifications import send_desktop_notification, send_email_alert

    tracker_lock = _get_tracker_lock(tracker_id)
    if not tracker_lock.acquire(blocking=False):
        print(
            f"[Scheduler] scan_skipped tracker_id={tracker_id} "
            f"trigger_source={trigger_source} reason=scan_already_in_progress"
        )
        return

    db = SessionLocal()
    try:
        tracker = (
            db.query(Tracker)
            .filter(Tracker.id == tracker_id, Tracker.active == True)
            .first()
        )
        if not tracker:
            return

        print(
            f"[{datetime.utcnow().strftime('%H:%M:%S')}] "
            f"Scanning tracker_id={tracker.id} name={tracker.name!r} "
            f"trigger_source={trigger_source} route={tracker.origin}->{tracker.destination} "
            f"window={tracker.window_start}..{tracker.window_end} "
            f"durations={tracker.duration_min}-{tracker.duration_max} "
            f"interval_hours={tracker.scan_interval_hours}"
        )

        result = scan_window(
            origin=tracker.origin,
            destination=tracker.destination,
            window_start=tracker.window_start,
            window_end=tracker.window_end,
            duration_min=tracker.duration_min,
            duration_max=tracker.duration_max,
            baggage_required=tracker.baggage_required,
            currency=tracker.currency,
            scan_context={
                "tracker_id": tracker.id,
                "tracker_name": tracker.name,
                "trigger_source": trigger_source,
                "window_start": tracker.window_start,
                "window_end": tracker.window_end,
                "duration_min": tracker.duration_min,
                "duration_max": tracker.duration_max,
                "scan_interval_hours": tracker.scan_interval_hours,
            },
        )

        tracker.last_scanned = datetime.utcnow()

        if result:
            snapshot = PriceSnapshot(
                tracker_id=tracker.id,
                total_price=result["total_price"],
                outbound_price=result.get("outbound_price"),
                return_price=result.get("return_price"),
                outbound_date=result.get("outbound_date"),
                return_date=result.get("return_date"),
                source=result.get("source", "amadeus"),
                booking_url=result.get("booking_url"),
                baggage_included=result.get("baggage_included", False),
                fare_class=result.get("fare_class"),
                currency=result.get("currency", "USD"),
            )
            db.add(snapshot)

            prev_price = tracker.current_best_price
            tracker.previous_best_price = prev_price
            tracker.current_best_price = result["total_price"]

            db.commit()

            # --- Alert logic ---
            price = result["total_price"]
            if tracker.target_price and price <= tracker.target_price:
                msg = (
                    f"{tracker.name}: {tracker.currency} {price:,.0f} "
                    f"(target: {tracker.currency} {tracker.target_price:,.0f})"
                )
                send_desktop_notification("✈ SkySync — Price Target Hit!", msg)
                if tracker.alert_email:
                    send_email_alert(
                        to_email=tracker.alert_email,
                        tracker_name=tracker.name,
                        price=price,
                        currency=tracker.currency,
                        booking_url=result.get("booking_url", ""),
                    )
        else:
            db.commit()
            print(
                f"[Scheduler] no_results tracker_id={tracker.id} "
                f"name={tracker.name!r} trigger_source={trigger_source}"
            )

    except Exception as exc:
        print(
            f"[Scheduler] scan_failed tracker_id={tracker_id} "
            f"trigger_source={trigger_source} error_type={type(exc).__name__} error={exc}"
        )
        try:
            db.rollback()
        except Exception:
            pass
    finally:
        db.close()
        tracker_lock.release()


def schedule_tracker(tracker_id: int, interval_hours: int) -> None:
    """Register or replace a periodic scan job."""
    job_id = f"tracker_{tracker_id}"
    if _scheduler.get_job(job_id):
        _scheduler.remove_job(job_id)
    
    # Enforce minimum interval of 1 hour to avoid excessive API calls
    interval_hours = max(1, interval_hours)
    
    _scheduler.add_job(
        scan_tracker,
        trigger=IntervalTrigger(hours=interval_hours),
        args=[tracker_id, "scheduled"],
        id=job_id,
        replace_existing=True,
        misfire_grace_time=3600,
        max_instances=1,
    )


def unschedule_tracker(tracker_id: int) -> None:
    job_id = f"tracker_{tracker_id}"
    if _scheduler.get_job(job_id):
        _scheduler.remove_job(job_id)


def start_scheduler() -> None:
    """Start the scheduler and restore jobs for all active trackers."""
    if not _scheduler.running:
        _scheduler.start()

    from database import SessionLocal
    from models import Tracker

    db = SessionLocal()
    try:
        trackers = db.query(Tracker).filter(Tracker.active == True).all()
        for t in trackers:
            schedule_tracker(t.id, t.scan_interval_hours)
        print(f"[Scheduler] Running — {len(trackers)} tracker job(s) restored.")
    finally:
        db.close()


def stop_scheduler() -> None:
    if _scheduler.running:
        _scheduler.shutdown(wait=False)


def trigger_scan_async(tracker_id: int, trigger_source: str = "manual") -> None:
    """Fire an immediate scan in a daemon thread (non-blocking)."""
    thread_name = f"scan-tracker-{tracker_id}-{trigger_source}"
    t = threading.Thread(
        target=scan_tracker,
        args=(tracker_id, trigger_source),
        daemon=True,
        name=thread_name,
    )
    t.start()


def trigger_all_scans_async() -> int:
    """Trigger immediate scans for all active trackers. Returns number of trackers queued."""
    from database import SessionLocal
    from models import Tracker

    db = SessionLocal()
    try:
        tracker_ids = [
            tracker_id
            for (tracker_id,) in db.query(Tracker.id).filter(Tracker.active == True).all()
        ]
    finally:
        db.close()

    for tracker_id in tracker_ids:
        trigger_scan_async(tracker_id, trigger_source="manual_all")

    return len(tracker_ids)
