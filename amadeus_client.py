"""
Amadeus API client for SkySync.

Free tier: Register at https://developers.amadeus.com/
Test environment returns synthetic but structurally correct data.
Switch AMADEUS_ENV=production for live prices (same free key, rate-limited).
"""

import os
import threading
import time
from datetime import date as date_type, timedelta
from typing import Any, Dict, List, Optional

from dotenv import load_dotenv

load_dotenv()


_client_lock = threading.Lock()
_request_lock = threading.Lock()
_shared_client = None
_last_request_started_at = 0.0
_MIN_REQUEST_INTERVAL_SECONDS = max(
    0.1,
    float(os.getenv("AMADEUS_MIN_REQUEST_INTERVAL_SECONDS", "0.35")),
)
_MAX_RETRIES = max(0, int(os.getenv("AMADEUS_MAX_RETRIES", "2")))
_BASE_RETRY_DELAY_SECONDS = max(
    0.25,
    float(os.getenv("AMADEUS_RETRY_BASE_DELAY_SECONDS", "1.5")),
)


def _get_client():
    global _shared_client
    from amadeus import Client
    if _shared_client is None:
        with _client_lock:
            if _shared_client is None:
                env = os.getenv("AMADEUS_ENV", "test")
                _shared_client = Client(
                    client_id=os.getenv("AMADEUS_CLIENT_ID", ""),
                    client_secret=os.getenv("AMADEUS_CLIENT_SECRET", ""),
                    hostname=env,
                )
    return _shared_client


def _get_env() -> str:
    return os.getenv("AMADEUS_ENV", "test")


def _format_log_context(context: Dict[str, Any]) -> str:
    parts = []
    for key, value in context.items():
        if value is None:
            continue
        parts.append(f"{key}={value}")
    return " ".join(parts)


def _build_request_context(
    origin: str,
    destination: str,
    depart_date: str,
    return_date: str,
    adults: int,
    currency: str,
    baggage_required: bool,
    max_offers: int,
    scan_context: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    context = {
        "env": _get_env(),
        "origin": origin,
        "destination": destination,
        "depart_date": depart_date,
        "return_date": return_date,
        "adults": adults,
        "currency": currency,
        "baggage_required": baggage_required,
        "max_offers": max_offers,
        "thread": threading.current_thread().name,
    }
    if scan_context:
        context.update({k: v for k, v in scan_context.items() if v is not None})
    return context


def _extract_error_details(exc: Exception) -> Dict[str, Any]:
    details: Dict[str, Any] = {
        "error_type": type(exc).__name__,
        "error": str(exc),
    }

    response = getattr(exc, "response", None)
    if response is None:
        return details

    status_code = getattr(response, "status_code", None)
    if status_code is not None:
        details["status_code"] = status_code

    http_response = getattr(response, "http_response", None)
    headers = getattr(http_response, "headers", None)
    if headers:
        for header_name in (
            "Retry-After",
            "X-RateLimit-Limit",
            "X-RateLimit-Remaining",
            "X-RateLimit-Reset",
        ):
            header_value = headers.get(header_name)
            if header_value is not None:
                details[header_name.lower().replace('-', '_')] = header_value

    result = getattr(response, "result", None)
    if isinstance(result, dict):
        if "errors" in result:
            details["api_errors"] = result["errors"]
        if "error" in result:
            details["api_error"] = result["error"]
        if "error_description" in result:
            details["api_error_description"] = result["error_description"]

    return details


def _sleep_for_retry(error_details: Dict[str, Any], attempt: int) -> float:
    retry_after = error_details.get("retry_after")
    if retry_after is not None:
        try:
            delay = float(retry_after)
        except (TypeError, ValueError):
            delay = _BASE_RETRY_DELAY_SECONDS * attempt
    else:
        delay = _BASE_RETRY_DELAY_SECONDS * attempt

    time.sleep(delay)
    return delay


def _execute_rate_limited_search(**kwargs):
    global _last_request_started_at

    with _request_lock:
        wait_seconds = _MIN_REQUEST_INTERVAL_SECONDS - (
            time.monotonic() - _last_request_started_at
        )
        if wait_seconds > 0:
            time.sleep(wait_seconds)

        _last_request_started_at = time.monotonic()
        amadeus = _get_client()
        return amadeus.shopping.flight_offers_search.get(**kwargs)


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
    """
    Build booking URL using Skyscanner, which has a predictable URL format.
    Skyscanner's URL format: 
    https://www.skyscanner.com/transport/flights/{origin}/{dest}/{depart}/{return}/
    Works reliably and opens with pre-filled search parameters.
    """
    # Ensure airport codes are uppercase (IATA standard)
    origin_code = origin.upper()
    dest_code = dest.upper()
    
    # Skyscanner uses YYMMDD format for dates (2-digit year)
    # Convert from YYYY-MM-DD to YYMMDD
    depart_parts = depart.split('-')
    depart_formatted = f"{depart_parts[0][2:]}{depart_parts[1]}{depart_parts[2]}"
    
    ret_parts = ret.split('-')
    ret_formatted = f"{ret_parts[0][2:]}{ret_parts[1]}{ret_parts[2]}"
    
    return (
        f"https://www.skyscanner.com/transport/flights/"
        f"{origin_code}/{dest_code}/{depart_formatted}/{ret_formatted}/"
        f"?adults=1&adultsv2=1&cabinclass=economy&children=0&childrenv2=&inboundaltsenabled=false"
        f"&infants=0&outboundaltsenabled=false&preferdirects=false&ref=home&rtn=1"
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
    scan_context: Optional[Dict[str, Any]] = None,
) -> List[Dict]:
    """Return a list of parsed round-trip offers for exact dates."""
    request_context = _build_request_context(
        origin=origin,
        destination=destination,
        depart_date=depart_date,
        return_date=return_date,
        adults=adults,
        currency=currency,
        baggage_required=baggage_required,
        max_offers=max_offers,
        scan_context=scan_context,
    )

    request_params = {
        "originLocationCode": origin,
        "destinationLocationCode": destination,
        "departureDate": depart_date,
        "returnDate": return_date,
        "adults": adults,
        "currencyCode": currency,
        "max": max_offers,
    }

    for attempt in range(1, _MAX_RETRIES + 2):
        try:
            resp = _execute_rate_limited_search(**request_params)
            return _parse_offers(
                resp=resp,
                origin=origin,
                destination=destination,
                depart_date=depart_date,
                return_date=return_date,
                baggage_required=baggage_required,
                currency=currency,
            )
        except Exception as exc:
            error_details = _extract_error_details(exc)
            status_code = error_details.get("status_code")
            log_context = dict(request_context)
            log_context.update(error_details)
            log_context["attempt"] = attempt

            if status_code == 429 and attempt <= _MAX_RETRIES:
                retry_delay = _sleep_for_retry(error_details, attempt)
                log_context["retry_delay_seconds"] = f"{retry_delay:.2f}"
                print(f"[Amadeus] rate_limited {_format_log_context(log_context)}")
                continue

            print(f"[Amadeus] search_round_trip_failed {_format_log_context(log_context)}")
            return []

    return []


def _parse_offers(
    resp,
    origin: str,
    destination: str,
    depart_date: str,
    return_date: str,
    baggage_required: bool,
    currency: str,
) -> List[Dict]:
    results = []
    for offer in resp.data:
        try:
            price = float(offer["price"]["grandTotal"])
        except (KeyError, ValueError):
            continue

        has_baggage = _check_baggage(offer)
        if baggage_required and not has_baggage:
            continue

        booking_url = _build_booking_url(origin, destination, depart_date, return_date)
        if "links" in offer and "flightOffers" in offer["links"]:
            booking_url = offer["links"]["flightOffers"]

        results.append(
            {
                "total_price": price,
                "outbound_price": None,
                "return_price": None,
                "outbound_date": depart_date,
                "return_date": return_date,
                "baggage_included": has_baggage,
                "fare_class": _get_fare_class(offer),
                "source": "amadeus",
                "booking_url": booking_url,
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
    scan_context: Optional[Dict[str, Any]] = None,
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
    request_count = 0
    while current <= end - timedelta(days=duration_min):
        # Try middle of the allowed duration range
        mid_dur = (duration_min + duration_max) // 2
        for dur in {duration_min, mid_dur, duration_max}:
            ret_dt = current + timedelta(days=dur)
            if ret_dt > end:
                continue
            request_count += 1
            request_context = dict(scan_context or {})
            request_context["scan_request_index"] = request_count
            offers = search_round_trip(
                origin=origin,
                destination=destination,
                depart_date=current.isoformat(),
                return_date=ret_dt.isoformat(),
                baggage_required=baggage_required,
                currency=currency,
                scan_context=request_context,
            )
            for o in offers:
                if o["total_price"] < best_price:
                    best_price = o["total_price"]
                    best = o

        current += timedelta(days=7)

    return best
