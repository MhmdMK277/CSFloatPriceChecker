"""Marketplace fee comparison.

Static, sourced fee table — no marketplace has a free public fee API, and
these change rarely. Skinport's commission is tiered by item price; the
others are flat. Sources (checked 2026-07): each platform's own fee page,
steamanalyst.com/guides/marketplaces, skinedge.net fee comparison.
"""

from __future__ import annotations

from typing import Any

# (threshold_cents_exclusive, fee_pct) — first bracket whose threshold
# exceeds the price wins. Skinport: 12% under $30, 9% to $100, 6% above.
SKINPORT_TIERS: list[tuple[int, float]] = [
    (3000, 12.0),
    (10000, 9.0),
    (10**9, 6.0),
]

MARKETPLACES: list[dict[str, Any]] = [
    {
        "key": "csfloat",
        "name": "CSFloat",
        "seller_fee_pct": 2.0,
        "payout": "USD (bank / crypto)",
        "note": "Lowest western fee; sales settle after the buyer receives the item.",
        "live_prices": True,
    },
    {
        "key": "buff163",
        "name": "Buff163",
        "seller_fee_pct": 2.5,
        "payout": "CNY (Alipay)",
        "note": "Biggest market, but withdrawing money is impractical without a Chinese bank account.",
        "live_prices": False,
    },
    {
        "key": "dmarket",
        "name": "DMarket",
        "seller_fee_pct": 5.0,
        "payout": "USD / crypto",
        "note": "Fee varies ~2-10% by item popularity; 5% is typical.",
        "live_prices": False,
    },
    {
        "key": "skinbaron",
        "name": "SkinBaron",
        "seller_fee_pct": 5.0,
        "payout": "EUR (bank)",
        "note": "EU-focused; flat 5% up to modest volumes.",
        "live_prices": False,
    },
    {
        "key": "skinport",
        "name": "Skinport",
        "seller_fee_pct": 12.0,  # headline rate; tiers applied in fee_pct_for
        "payout": "EUR/USD (bank)",
        "note": "Tiered fee: 12% under $30, 9% to $100, 6% above. Fast payouts, strong buyer traffic.",
        "live_prices": True,
    },
    {
        "key": "steam",
        "name": "Steam Market",
        "seller_fee_pct": 15.0,
        "payout": "Steam wallet only",
        "note": "Proceeds can never leave Steam — fine for buying more skins, useless for cashing out.",
        "live_prices": False,
    },
]


def fee_pct_for(key: str, price_cents: int) -> float:
    if key == "skinport":
        for threshold, pct in SKINPORT_TIERS:
            if price_cents < threshold:
                return pct
    market = next((m for m in MARKETPLACES if m["key"] == key), None)
    return market["seller_fee_pct"] if market else 0.0


def sale_breakdown(price_cents: int) -> list[dict[str, Any]]:
    """Net payout per marketplace if an item sells at ``price_cents``."""
    out = []
    for market in MARKETPLACES:
        pct = fee_pct_for(market["key"], price_cents)
        fee = round(price_cents * pct / 100)
        out.append({
            **market,
            "seller_fee_pct": pct,
            "fee_cents": fee,
            "net_cents": price_cents - fee,
        })
    return sorted(out, key=lambda m: -m["net_cents"])
