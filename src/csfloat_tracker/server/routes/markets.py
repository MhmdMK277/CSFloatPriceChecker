"""Marketplace fee comparison and cross-market price data."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ...core.markets import MARKETPLACES, sale_breakdown
from ..deps import AppContext, get_ctx

router = APIRouter()


@router.get("/markets/fees")
async def fees(price_cents: int | None = Query(None, ge=0, le=100_000_000)):
    """The fee table; with ``price_cents``, also the net payout per market."""
    if price_cents is None:
        return {"marketplaces": MARKETPLACES}
    return {"marketplaces": sale_breakdown(price_cents)}


@router.get("/markets/compare")
async def compare(
    name: str = Query(..., description="market_hash_name"),
    ctx: AppContext = Depends(get_ctx),
):
    """Buy prices + net sell payouts for one item across marketplaces.

    CSFloat's price is the catalog reference; Skinport's is live from the
    cached public feed. Markets without a data source report fees only.
    """
    variant = ctx.itemdb.lookup(name)
    csfloat_cents = variant.reference_price_cents if variant else None
    skinport = await ctx.storage.get_skinport_price(name)
    skinport_status = await ctx.storage.skinport_status()

    # Sell breakdown anchored on the best-known price for the item.
    anchor = csfloat_cents or (skinport["min_price_cents"] if skinport else None)
    return {
        "market_hash_name": name,
        "buy": {
            "csfloat_reference_cents": csfloat_cents,
            "skinport_min_cents": skinport["min_price_cents"] if skinport else None,
            "skinport_quantity": skinport["quantity"] if skinport else None,
            "skinport_updated_at": skinport["updated_at"] if skinport else None,
        },
        "sell": sale_breakdown(anchor) if anchor else [],
        "skinport_feed": skinport_status,
    }
