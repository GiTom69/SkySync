"""
Amadeus API client for SkySync.

Free tier: Register at https://developers.amadeus.com/
Test environment returns synthetic but structurally correct data.
Switch AMADEUS_ENV=production for live prices (same free key, rate-limited).
"""

import os
from datetime import date as date_type, timedelta
from typing import List, Dict, Optional

from dotenv import load_dotenv

load_dotenv()


def _get_client():
    from amadeus import Client
    env = os.getenv("AMADEUS_ENV", "test")
    return Client(
        client_id=os.getenv("AMADEUS_CLIENT_ID", ""),
        client_secret=os.getenv("AMADEUS_CLIENT_SECRET", ""),
        hostname=env,
    )


def _check_baggage(offer: dict) -> bool:
    """Return True if at least one checked bag or carry-on is included."""
    try:
        for tp in offer.get("travelerPricings", []):
            for fd in tp.get("fareDetailsBySegment", []):
                bags = fd.get("includedCheckedBags", {})
                if bags.get("quantity", 0) > 0 or bags.get("weight", 0) > 0:
                    return True
                if fd.get("cabin", "") in ("BUSINESS", "FIRST", "PREMIUM_ECONOMY"):
                    return True
    except Exception:
        pass
    return False


def _get_fare_class(offer: dict) -> str:
    try:
        tps = offer.get("travelerPricings", [])
        if tps:
            fds = tps[0].get("fareDetailsBySegment", [])
            if fds:
                return fds[0].get("cabin", "ECONOMY")
    except Exception:
        pass
    return "ECONOMY"


def _build_booking_url(origin: str, dest: str, depart: str, ret: str) -> str:
    return (
        f"https://www.google.com/flights#search;f={origin};t={dest}"
        f";d={depart};r={ret};tt=r"
    )


def search_round_trip(
    origin: str,
    destination: str,
    depart_date: str,
    return_date: str,
    adults: int = 1,
    currency: str = "USD",
    baggage_required: bool = False,
    max_offers: int = 5,
) -> List[Dict]:
    """Return a list of parsed round-trip offers for exact dates."""
    try:
        amadeus = _get_client()
        resp = amadeus.shopping.flight_offers_search.get(
            originLocationCode=origin,
            destinationLocationCode=destination,
            departureDate=depart_date,
            returnDate=return_date,
            adults=adults,
            currencyCode=currency,
            max=max_offers,
        )
    except Exception as e:
        print(f"[Amadeus] search_round_trip error ({depart_date}→{return_date}): {e}")
        return []

    results = []
    for offer in resp.data:
        try:
            price = float(offer["price"]["grandTotal"])
        except (KeyError, ValueError):
            continue

        has_baggage = _check_baggage(offer)
        if baggage_required and not has_baggage:
            continue

        results.append(
            {
                "total_price": price,
                "outbound_price": None,  # Amadeus doesn't split per-leg in v2
                "return_price": None,
                "outbound_date": depart_date,
                "return_date": return_date,
                "baggage_included": has_baggage,
                "fare_class": _get_fare_class(offer),
                "source": "amadeus",
                "booking_url": _build_booking_url(origin, destination, depart_date, return_date),
                "currency": currency,
            }
        )
    return results


def scan_window(
    origin: str,
    destination: str,
    window_start: str,
    window_end: str,
    duration_min: int,
    duration_max: int,
    baggage_required: bool = False,
    currency: str = "USD",
) -> Optional[Dict]:
    """
    Sample the date window (weekly steps) and return the single cheapest offer found.
    Weekly steps keep API calls reasonable on the free tier (~20 calls per scan).
    """
    start = date_type.fromisoformat(window_start)
    end = date_type.fromisoformat(window_end)

    best: Optional[Dict] = None
    best_price = float("inf")

    current = start
    while current <= end - timedelta(days=duration_min):
        # Try middle of the allowed duration range
        mid_dur = (duration_min + duration_max) // 2
        for dur in {duration_min, mid_dur, duration_max}:
            ret_dt = current + timedelta(days=dur)
            if ret_dt > end:
                continue
            offers = search_round_trip(
                origin=origin,
                destination=destination,
                depart_date=current.isoformat(),
                return_date=ret_dt.isoformat(),
                baggage_required=baggage_required,
                currency=currency,
            )
            for o in offers:
                if o["total_price"] < best_price:
                    best_price = o["total_price"]
                    best = o

        current += timedelta(days=7)

    return best
