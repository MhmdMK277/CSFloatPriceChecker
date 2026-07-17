"""Marketplace fee comparison for buy/sell decisions."""

from __future__ import annotations

from fastapi import APIRouter, Query

from ...core.markets import MARKETPLACES, sale_breakdown

router = APIRouter()


@router.get("/markets/fees")
async def fees(price_cents: int | None = Query(None, ge=0, le=100_000_000)):
    """The fee table; with ``price_cents``, also the net payout per market."""
    if price_cents is None:
        return {"marketplaces": MARKETPLACES}
    return {"marketplaces": sale_breakdown(price_cents)}
