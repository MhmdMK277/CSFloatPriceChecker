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


class _FakeVariant:
    def __init__(self, min_float=0.0, max_float=1.0, reference_price_cents=None):
        self.min_float = min_float
        self.max_float = max_float
        self.reference_price_cents = reference_price_cents


class _FakeItemDb:
    def __init__(self, variants: dict):
        self._variants = variants

    def lookup(self, name):
        return self._variants.get(name)


def test_deal_reason_low_float():
    from csfloat_tracker.core.stats import deal_reason

    # FT bracket is 0.15-0.38; float 0.151 is ~top 0.4%
    listing = Listing.from_api(make_listing(price=2000, float_value=0.1505))
    db = _FakeItemDb({
        "AK-47 | Redline (Field-Tested)": _FakeVariant(0.10, 0.70, 2894),
    })
    reason = deal_reason(listing, db)
    assert "top 1% float for FT" in reason


def test_deal_reason_cross_wear():
    from csfloat_tracker.core.stats import deal_reason

    # FT listing priced under the MW reference
    listing = Listing.from_api(make_listing(price=3000, float_value=0.30))
    db = _FakeItemDb({
        "AK-47 | Redline (Field-Tested)": _FakeVariant(0.10, 0.70, 2894),
        "AK-47 | Redline (Minimal Wear)": _FakeVariant(0.10, 0.70, 3500),
    })
    reason = deal_reason(listing, db)
    assert "costs less than the MW reference" in reason


def test_deal_reason_stickers():
    from csfloat_tracker.core.stats import deal_reason

    raw = make_listing(price=2000, float_value=0.30)
    raw["item"]["stickers"] = [
        {"name": "Sticker | Katowice", "slot": 0, "reference": {"price": 120000}},
    ]
    listing = Listing.from_api(raw)
    reason = deal_reason(listing, _FakeItemDb({}))
    assert "$1200 in stickers" in reason


def test_deal_reason_none_when_unremarkable():
    from csfloat_tracker.core.stats import deal_reason

    listing = Listing.from_api(make_listing(price=2000, float_value=0.30))
    db = _FakeItemDb({"AK-47 | Redline (Field-Tested)": _FakeVariant(0.10, 0.70, 2894)})
    assert deal_reason(listing, db) is None


def test_marketplace_sale_breakdown():
    from csfloat_tracker.core.markets import sale_breakdown

    rows = {r["key"]: r for r in sale_breakdown(10000)}  # $100 sale
    assert rows["csfloat"]["net_cents"] == 9800
    assert rows["steam"]["net_cents"] == 8500
    assert rows["buff163"]["fee_cents"] == 250
    # Sorted best-net-first, and nets never exceed gross
    ordered = sale_breakdown(10000)
    assert ordered[0]["key"] == "csfloat"
    assert all(r["net_cents"] <= 10000 for r in rows.values())


def test_skinport_tiered_fees():
    from csfloat_tracker.core.markets import fee_pct_for, sale_breakdown

    assert fee_pct_for("skinport", 2000) == 12.0   # $20
    assert fee_pct_for("skinport", 5000) == 9.0    # $50
    assert fee_pct_for("skinport", 50000) == 6.0   # $500
    # $100 exactly crosses into the 6% tier
    assert fee_pct_for("skinport", 10000) == 6.0
    rows = {r["key"]: r for r in sale_breakdown(2000)}
    assert rows["skinport"]["net_cents"] == 2000 - 240


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
