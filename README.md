# ✈ SkySync 2.0 — Flight Intelligence Dashboard

Automated flight price tracker with buy/wait AI signals, email alerts, and a beautiful mission-control dashboard.

---

## ⚡ Quick Start

### 1. Get a Free Amadeus API Key

1. Register at **https://developers.amadeus.com/** (free)
2. Create a new app → copy your **Client ID** and **s Secret**
3. The **test environment** returns synthetic (but structurally correct) data — great for development
4. Switch to **production** with the same keys for real live prices

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env and paste your Amadeus credentials
```

### 3. Install dependencies

```bash
python -m venv venv
source venv/Scripts/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Run the app

```bash
uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

Open **http://localhost:8000** in your browser.

---

## 🗂 Project Structure

```
skysync/
├── main.py             # FastAPI app — routes, startup, shutdown
├── models.py           # SQLAlchemy ORM models (Tracker, PriceSnapshot)
├── database.py         # SQLite engine + session factory
├── amadeus_client.py   # Amadeus API wrapper + window scanning logic
├── analytics.py        # Buy/Wait signal (numpy linear regression)
├── scheduler.py        # APScheduler background scan jobs
├── notifications.py    # Desktop (plyer) + email (SMTP) alerts
├── requirements.txt
├── .env.example
└── templates/
    └── index.html      # Single-page dashboard (Chart.js + vanilla JS)
```

---

## 🔧 How It Works

1. **Create a Tracker** — Enter origin/destination (IATA codes), trip duration, and the date window you're willing to travel.
2. **Initial Scan** — Fires immediately in a background thread. SkySync queries the Amadeus API across weekly date samples in your window, finding the current cheapest round-trip.
3. **Periodic Scans** — APScheduler fires every N hours (you choose). Each scan stores a `PriceSnapshot` in SQLite.
4. **Buy Signal** — After 3+ data points, a numpy linear regression on the recent price window classifies the trend as UP/DOWN/FLAT and issues a BUY/WAIT/NEUTRAL recommendation with a confidence score.
5. **Alerts** — If the price drops below your target, a desktop notification fires (via `plyer`) and an email is sent if configured.

---

## 📡 API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/` | Dashboard UI |
| GET | `/api/trackers` | List all active trackers |
| POST | `/api/trackers` | Create a new tracker |
| DELETE | `/api/trackers/{id}` | Deactivate a tracker |
| POST | `/api/trackers/{id}/scan` | Trigger an immediate scan |
| GET | `/api/trackers/{id}/history` | Price history + buy signal |
| GET | `/api/stats` | Dashboard aggregate stats |

---

## 📧 Email Alerts

Set these in `.env`:

```env
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=you@gmail.com
SMTP_PASS=your_app_password   # use a Gmail App Password, not your account password
```

---

## 🚀 Switching to Production Prices

In `.env`, change:

```env
AMADEUS_ENV=production
```

The same free Amadeus key works in production with a generous rate limit (1 req/100ms, 1000 calls/month on the free tier).

---

## 💡 Tips

- **IATA Codes**: TLV (Tel Aviv), NRT (Tokyo Narita), LHR (London Heathrow), JFK, LAX, etc.
- **Date Windows**: Keep windows under 3 months to get meaningful scan samples.
- **Scan Interval**: 6 hours is a good default. Prices rarely change faster than this.
- **Rate Limits**: The scanner uses weekly steps across your window. A 3-month window = ~12 API calls per scan, well within free-tier limits.
