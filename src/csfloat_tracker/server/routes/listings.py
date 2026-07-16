"""Live CSFloat listings proxy with normalized filters."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from ...core.stats import discount_pct, summarize_listings
from ..deps import AppContext, get_ctx

router = APIRouter()

CATEGORY_MAP = {"normal": 1, "stattrak": 2, "souvenir": 3}
WEAR_RANGES = {
    "FN": (0.00, 0.07),
    "MW": (0.07, 0.15),
    "FT": (0.15, 0.38),
    "WW": (0.38, 0.45),
    "BS": (0.45, 1.00),
}


@router.get("/listings")
async def get_listings(
    name: str | None = Query(None, description="market_hash_name"),
    wear: str | None = Query(None, pattern="^(FN|MW|FT|WW|BS)$"),
    min_float: float | None = Query(None, ge=0, le=1),
    max_float: float | None = Query(None, ge=0, le=1),
    min_price: int | None = Query(None, ge=0, description="cents"),
    max_price: int | None = Query(None, ge=0, description="cents"),
    category: str | None = Query(None, pattern="^(normal|stattrak|souvenir)$"),
    sort_by: str = Query("lowest_price"),
    type: str | None = Query(None, pattern="^(buy_now|auction)$"),
    paint_seed: int | None = Query(None),
    paint_index: int | None = Query(None),
    def_index: int | None = Query(None),
    cursor: str | None = Query(None),
    limit: int = Query(50, ge=1, le=50),
    ctx: AppContext = Depends(get_ctx),
):
    """Search live listings. Wear shorthand expands to a float range unless
    an explicit float range is given."""
    params: dict = {
        "market_hash_name": name,
        "min_float": min_float,
        "max_float": max_float,
        "min_price": min_price,
        "max_price": max_price,
        "sort_by": sort_by,
        "type": type,
        "paint_seed": paint_seed,
        "paint_index": paint_index,
        "def_index": def_index,
        "cursor": cursor,
        "limit": limit,
    }
    if wear and min_float is None and max_float is None:
        lo, hi = WEAR_RANGES[wear]
        params["min_float"], params["max_float"] = lo, hi
    if category:
        params["category"] = CATEGORY_MAP[category]

    page = await ctx.client.get_listings(**params)

    reference = None
    if name:
        variant = ctx.itemdb.lookup(name)
        if variant and variant.reference_price_cents:
            reference = variant.reference_price_cents

    results = []
    for listing in page.listings:
        item = listing.to_public()
        ref = listing.reference_price_cents or reference
        item["discount_pct"] = discount_pct(listing.price_cents, ref) if ref else None
        results.append(item)

    return {
        "listings": results,
        "cursor": page.cursor,
        "summary": summarize_listings(page.listings),
        "reference_price_cents": reference,
        "rate": ctx.client.rate_status().get("listings"),
    }


@router.get("/listings/{listing_id}")
async def get_listing(listing_id: str, ctx: AppContext = Depends(get_ctx)):
    listing = await ctx.client.get_listing(listing_id)
    return listing.to_public()
