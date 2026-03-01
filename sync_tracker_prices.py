"""Utility script to sync tracker current_best_price with latest snapshot."""
from database import SessionLocal
from models import Tracker, PriceSnapshot

db = SessionLocal()
try:
    trackers = db.query(Tracker).filter(Tracker.active == True).all()
    
    for tracker in trackers:
        latest_snap = (
            db.query(PriceSnapshot)
            .filter(PriceSnapshot.tracker_id == tracker.id)
            .order_by(PriceSnapshot.scanned_at.desc())
            .first()
        )
        
        if latest_snap:
            old_price = tracker.current_best_price
            tracker.current_best_price = latest_snap.total_price
            if old_price is None:
                tracker.previous_best_price = latest_snap.total_price
            print(f"Tracker {tracker.id} ({tracker.name}): ${latest_snap.total_price}")
        else:
            print(f"Tracker {tracker.id} ({tracker.name}): No snapshots yet")
    
    db.commit()
    print("\n✓ All tracker prices synced")
finally:
    db.close()
