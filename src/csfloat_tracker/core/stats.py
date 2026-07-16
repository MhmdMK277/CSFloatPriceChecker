"""Price statistics: listing summaries, trends and deal scoring."""

from __future__ import annotations

import statistics
from typing import Any

from .models import Listing


def summarize_listings(listings: list[Listing]) -> dict[str, Any]:
    """Aggregate a page of listings into snapshot-ready stats."""
    prices = [x.price_cents for x in listings if x.price_cents > 0]
    floats = [x.float_value for x in listings if x.float_value is not None]
    if not prices:
        return {
            "min_price_cents": None, "avg_price_cents": None,
            "median_price_cents": None, "listing_count": 0, "min_float": None,
        }
    return {
        "min_price_cents": min(prices),
        "avg_price_cents": round(statistics.mean(prices)),
        "median_price_cents": round(statistics.median(prices)),
        "listing_count": len(prices),
        "min_float": min(floats) if floats else None,
    }


def discount_pct(price_cents: int, reference_cents: int) -> float:
    """How far below the reference price a listing sits, as a percentage."""
    if reference_cents <= 0:
        return 0.0
    return round((1 - price_cents / reference_cents) * 100, 2)


def trend(snapshots: list[dict[str, Any]], *, threshold_pct: float = 1.0) -> str:
    """Classify recent movement as 'up', 'down' or 'stable'.

    Compares the newest snapshot's min price with the average min price of
    the preceding window (up to 10 points).
    """
    prices = [s["min_price_cents"] for s in snapshots if s.get("min_price_cents")]
    if len(prices) < 2:
        return "stable"
    latest = prices[-1]
    window = prices[-11:-1]
    base = statistics.mean(window)
    if base <= 0:
        return "stable"
    change = (latest - base) / base * 100
    if change > threshold_pct:
        return "up"
    if change < -threshold_pct:
        return "down"
    return "stable"


def history_summary(snapshots: list[dict[str, Any]]) -> dict[str, Any]:
    """Headline numbers for a price-history chart."""
    mins = [s["min_price_cents"] for s in snapshots if s.get("min_price_cents")]
    if not mins:
        return {"lowest_cents": None, "highest_cents": None, "latest_cents": None,
                "change_pct": None, "trend": "stable", "points": 0}
    latest = mins[-1]
    first = mins[0]
    return {
        "lowest_cents": min(mins),
        "highest_cents": max(mins),
        "latest_cents": latest,
        "change_pct": round((latest - first) / first * 100, 2) if first else None,
        "trend": trend(snapshots),
        "points": len(mins),
    }


def portfolio_summary(entries: list[dict[str, Any]], current_prices: dict[str, int | None]) -> dict[str, Any]:
    """P&L rollup: entries carry buy price; current prices come per name."""
    total_cost = 0
    total_value = 0
    priced = 0
    rows = []
    for e in entries:
        qty = e.get("quantity") or 1
        cost = e["buy_price_cents"] * qty
        current = current_prices.get(e["market_hash_name"])
        value = (current or 0) * qty
        total_cost += cost
        if current is not None:
            total_value += value
            priced += 1
        pnl = value - cost if current is not None else None
        rows.append({
            **e,
            "current_price_cents": current,
            "pnl_cents": pnl,
            "roi_pct": round(pnl / cost * 100, 2) if pnl is not None and cost else None,
        })
    return {
        "entries": rows,
        "total_cost_cents": total_cost,
        "total_value_cents": total_value,
        "total_pnl_cents": total_value - total_cost if priced else None,
        "priced_entries": priced,
    }
