"""
Lightweight price analytics for the Buy Now / Wait signal.
Uses numpy linear regression — no heavy ML deps required.
"""

from typing import List, Optional, Dict
import numpy as np


def get_buy_signal(prices: List[float], min_points: int = 3) -> Dict:
    """
    Analyse recent price history and return a buy/wait recommendation.

    Returns:
        {
            signal:        "BUY" | "WAIT" | "NEUTRAL",
            confidence:    0.0 – 1.0,
            trend:         "UP" | "DOWN" | "FLAT" | "INSUFFICIENT_DATA",
            predicted_next: float | None,
            slope:         float,
            pct_change:    float   (% change from first to last in window)
        }
    """
    if len(prices) < min_points:
        return {
            "signal": "NEUTRAL",
            "confidence": 0.0,
            "trend": "INSUFFICIENT_DATA",
            "predicted_next": None,
            "slope": 0.0,
            "pct_change": 0.0,
        }

    # Use the last 10 data points to reduce noise
    window = np.array(prices[-10:], dtype=float)
    x = np.arange(len(window), dtype=float)
    mean_price = float(np.mean(window))

    # Fit linear trend
    coeffs = np.polyfit(x, window, 1)
    slope = float(coeffs[0])
    predicted_next = float(np.polyval(coeffs, len(window)))

    # Slope as % of mean price per step
    pct_slope = slope / mean_price if mean_price > 0 else 0.0

    # Overall % change across the window
    pct_change = float((window[-1] - window[0]) / window[0] * 100) if window[0] > 0 else 0.0

    # Historical position: where does current price sit relative to window min/max?
    h_min, h_max = float(np.min(window)), float(np.max(window))
    if h_max > h_min:
        position = (window[-1] - h_min) / (h_max - h_min)  # 0 = at bottom, 1 = at top
    else:
        position = 0.5

    # Classify trend
    if pct_slope > 0.02:
        trend = "UP"
    elif pct_slope < -0.02:
        trend = "DOWN"
    else:
        trend = "FLAT"

    # Determine signal
    if trend == "UP":
        # Prices rising — buy now before they go higher
        signal = "BUY"
        confidence = min(0.5 + abs(pct_slope) * 5, 0.95)
    elif trend == "DOWN":
        # Prices falling — might be worth waiting, unless near historical low
        if position < 0.15:
            # Already at the bottom, unlikely to fall much more
            signal = "BUY"
            confidence = 0.70
        else:
            signal = "WAIT"
            confidence = min(0.5 + abs(pct_slope) * 5, 0.90)
    else:
        # Flat — if near historical low, buy; otherwise neutral
        if position < 0.20:
            signal = "BUY"
            confidence = 0.65
        elif position > 0.80:
            signal = "WAIT"
            confidence = 0.55
        else:
            signal = "NEUTRAL"
            confidence = 0.40

    return {
        "signal": signal,
        "confidence": round(confidence, 2),
        "trend": trend,
        "predicted_next": round(predicted_next, 2),
        "slope": round(slope, 2),
        "pct_change": round(pct_change, 2),
    }
