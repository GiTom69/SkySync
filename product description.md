Here's the updated product description and tech stack:

---

## SkySync 2.0 — Product Description

**Overview**
SkySync is a smart, automated flight-tracking desktop and web application that eliminates the tedium of manual flight hunting. Rather than scraping volatile consumer-facing websites, SkySync integrates with legitimate, stable flight data APIs — primarily the **Amadeus for Developers API** (free tier) and **Duffel API** (free sandbox) — to pull live and historical pricing data across multiple carriers. The result is a single, sleek dashboard that tells you not just the current price, but whether you should buy now or wait.

**Target Audience**
Budget-conscious travelers, digital nomads, and frequent flyers who want to optimize travel spending without spending hours refreshing browser tabs.

---

**Core Features**

*Stable, API-Driven Multi-Source Aggregation* — Instead of fragile web scraping, SkySync queries the Amadeus and Duffel APIs for live pricing across hundreds of airlines and routes. This keeps the app legally sound, bot-resistant, and far more reliable than DOM-scraping Google Flights or KAYAK.

*Customizable Search Windows* — Users input their origin, destination, and a flexible travel window (e.g., "Any 10–14 day trip between October 1st and November 30th"). SkySync automatically permutes every valid outbound/return date combination within that window and queries each one.

*Baggage & Fare Class Filtering* — A toggle lets users exclude Basic Economy fares that omit carry-on luggage, filtering results to only show fares that include the selected baggage allowance. No more discovering hidden fees at checkout.

*Split-Direction Price History* — SkySync tracks and graphs outbound and return legs independently. Users can see at a glance whether the TLV→NRT or NRT→TLV leg is driving the price spike.

*Split-Ticketing Engine* — The app evaluates whether two separate one-way tickets (on different carriers, sourced from different API results) produce a lower combined fare than any available round-trip, then surfaces that as a "Split Deal" option with a clear savings badge.

*Set-and-Forget Periodic Scanning* — Users define their preferred scan interval (e.g., every 6 hours, once daily). SkySync runs quietly in the background via a scheduled job, updating its local database without any manual intervention.

*AI-Powered Buy Signal* — Because SkySync accumulates a rich price history for every tracked route, it runs a lightweight time-series forecasting model (Facebook Prophet or a simple ARIMA model) on that data. Each tracker displays a "Buy Now / Wait" recommendation alongside a confidence score, based on whether the model predicts the price is near a local minimum or still trending downward.

*Smart Threshold Alerts* — Users set a target price per tracker. The moment any scan returns a fare combination below that threshold, SkySync fires a desktop notification (via `plyer`) and optionally sends an email alert.

*Modern, Uncluttered GUI* — A dark-mode-ready, minimalist dashboard built with a Python-native or lightweight web frontend. Each tracker card shows the current best price, a green/red price-change indicator, the AI buy signal, and an interactive price-history line graph. Clicking any data point on the graph deep-links directly to the booking page on the originating platform.

---

**User Flow**

1. **Create a Tracker** — Enter origin (e.g., TLV), destination (e.g., NRT), preferred trip duration (e.g., 14 days), and baggage preference.
2. **Set the Window** — Select the overarching date range you're willing to travel.
3. **Deploy** — Click "Start Tracking." The dashboard populates with the current lowest fares (including any split-ticket deals) and begins logging data points.
4. **Read the Signal** — The AI indicator updates with each scan cycle, showing "Buy Now" when the model detects the price is at or near a trough.
5. **Analyze & Book** — When the price drops or the signal fires, click the fare card to be redirected to the exact booking link on the originating platform.

---

## Tech Stack

**Language:** Python 3.11+

**Data & APIs**
- `amadeus` (official Amadeus Python SDK) — flight search, price confirmation, fare details including baggage
- `duffel-api-python` — secondary source for fare comparison and one-way ticket pricing
- `requests` + `httpx` — general HTTP calls and async API requests

**Scheduling & Background Jobs**
- `APScheduler` — lightweight in-process job scheduler for periodic scans; no separate message broker needed at this scale

**Database**
- `SQLite` via `SQLAlchemy` ORM — local, zero-config storage for price history, trackers, and alerts; easily swappable to PostgreSQL if a hosted/multi-user version is desired

**Predictive Analytics**
- `prophet` (Facebook/Meta Prophet) — time-series forecasting for the Buy Now / Wait signal
- `pandas` + `numpy` — data wrangling and feature preparation
- `scikit-learn` — fallback linear regression for routes with sparse history

**Alerting**
- `plyer` — cross-platform desktop notifications
- `smtplib` (stdlib) — email alerts via any SMTP provider (Gmail, etc.)

**Frontend / GUI** (choose one path)
- *Desktop app:* `PyQt6` or `customtkinter` with `matplotlib` embedded charts — fully offline, single executable via `PyInstaller`
- *Web app:* `FastAPI` backend + `Jinja2` templates + `Chart.js` for interactive graphs — runs locally on `localhost`, accessible from any browser; `Uvicorn` as the ASGI server

**Packaging & Environment**
- `Poetry` — dependency management
- `python-dotenv` — API key and config management
- `PyInstaller` (desktop path) or `Docker` (web path) — distribution

---

This stack uses exclusively free and open-source tools. The Amadeus API has a generous free tier for the test environment and a self-serve production key with no upfront cost. Duffel offers a free sandbox. Everything else is MIT/Apache-licensed Python tooling.