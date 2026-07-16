from csfloat_tracker.core.models import Listing
from csfloat_tracker.core.stats import (
    discount_pct,
    history_summary,
    portfolio_summary,
    summarize_listings,
    trend,
)

from .conftest import make_listing


def _listings(prices: list[int]) -> list[Listing]:
    return [Listing.from_api(make_listing(listing_id=str(i), price=p)) for i, p in enumerate(prices)]


def test_summarize_listings():
    s = summarize_listings(_listings([1000, 2000, 3000]))
    assert s["min_price_cents"] == 1000
    assert s["avg_price_cents"] == 2000
    assert s["median_price_cents"] == 2000
    assert s["listing_count"] == 3
    assert s["min_float"] == 0.23


def test_summarize_empty():
    s = summarize_listings([])
    assert s["listing_count"] == 0
    assert s["min_price_cents"] is None


def test_discount_pct():
    assert discount_pct(8000, 10000) == 20.0
    assert discount_pct(10000, 10000) == 0.0
    assert discount_pct(11000, 10000) == -10.0
    assert discount_pct(500, 0) == 0.0


def _snaps(prices: list[int]) -> list[dict]:
    return [{"min_price_cents": p} for p in prices]


def test_trend():
    assert trend(_snaps([100, 100, 100, 100])) == "stable"
    assert trend(_snaps([100, 100, 100, 110])) == "up"
    assert trend(_snaps([100, 100, 100, 90])) == "down"
    assert trend(_snaps([100])) == "stable"
    assert trend([]) == "stable"


def test_history_summary():
    h = history_summary(_snaps([100, 150, 120]))
    assert h["lowest_cents"] == 100
    assert h["highest_cents"] == 150
    assert h["latest_cents"] == 120
    assert h["change_pct"] == 20.0
    assert h["points"] == 3


def test_portfolio_summary():
    entries = [
        {"id": 1, "market_hash_name": "A", "buy_price_cents": 1000, "quantity": 2},
        {"id": 2, "market_hash_name": "B", "buy_price_cents": 500, "quantity": 1},
    ]
    result = portfolio_summary(entries, {"A": 1500, "B": None})
    assert result["total_cost_cents"] == 2500
    assert result["total_value_cents"] == 3000
    row_a = result["entries"][0]
    assert row_a["pnl_cents"] == 1000
    assert row_a["roi_pct"] == 50.0
    row_b = result["entries"][1]
    assert row_b["pnl_cents"] is None
