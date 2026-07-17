"""Marketplace fee comparison.

Static, sourced fee table — no marketplace has a free public fee API, and
these change rarely. Percentages are the standard seller commission each
platform advertises; several have volume/value tiers, noted per entry.
Sources (checked 2026-07): steamanalyst.com/guides/marketplaces,
skinedge.net/compare/cs2-marketplace-fees-comparison, each platform's own
fee page.
"""

from __future__ import annotations

from typing import Any

MARKETPLACES: list[dict[str, Any]] = [
    {
        "key": "csfloat",
        "name": "CSFloat",
        "seller_fee_pct": 2.0,
        "payout": "USD (bank / crypto)",
        "note": "Lowest western fee; sales settle after the buyer receives the item.",
    },
    {
        "key": "buff163",
        "name": "Buff163",
        "seller_fee_pct": 2.5,
        "payout": "CNY (Alipay)",
        "note": "Biggest market, but withdrawing money is impractical without a Chinese bank account.",
    },
    {
        "key": "dmarket",
        "name": "DMarket",
        "seller_fee_pct": 5.0,
        "payout": "USD / crypto",
        "note": "Fee varies ~2-10% by item popularity; 5% is typical.",
    },
    {
        "key": "skinport",
        "name": "Skinport",
        "seller_fee_pct": 12.0,
        "payout": "EUR/USD (bank)",
        "note": "Drops to ~6% for items over $1,000. Fast payouts, strong buyer traffic.",
    },
    {
        "key": "steam",
        "name": "Steam Market",
        "seller_fee_pct": 15.0,
        "payout": "Steam wallet only",
        "note": "Proceeds can never leave Steam — fine for buying more skins, useless for cashing out.",
    },
]


def sale_breakdown(price_cents: int) -> list[dict[str, Any]]:
    """Net payout per marketplace if an item sells at ``price_cents``."""
    out = []
    for market in MARKETPLACES:
        fee = round(price_cents * market["seller_fee_pct"] / 100)
        out.append({
            **market,
            "fee_cents": fee,
            "net_cents": price_cents - fee,
        })
    return out
