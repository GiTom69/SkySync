"""Check database state"""
from database import SessionLocal
from models import PriceSnapshot, Tracker

db = SessionLocal()

snapshots = db.query(PriceSnapshot).all()
print(f'Total snapshots in DB: {len(snapshots)}')
for s in snapshots[:10]:
    print(f'  - Tracker {s.tracker_id}: {s.currency} {s.total_price:.2f} at {s.scanned_at}')

trackers = db.query(Tracker).all()
print(f'\nTotal trackers: {len(trackers)}')
for t in trackers:
    print(f'  - ID{t.id} {t.name}: last_scanned={t.last_scanned}, active={t.active}')
    
db.close()
