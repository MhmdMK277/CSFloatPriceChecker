"""Item autocomplete and catalog metadata."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query

from ...core.schema_parser import expand_image
from ..deps import AppContext, get_ctx

router = APIRouter()


def _variant_payload(v, ctx: AppContext) -> dict:
    d = v.model_dump()
    d["image"] = expand_image(v.image)
    d["collection_names"] = [ctx.itemdb.collections.get(c, c) for c in v.collections]
    d["rarity_name"] = ctx.itemdb.rarities.get(v.rarity) if v.rarity is not None else None
    return d


@router.get("/search")
async def autocomplete(
    q: str = Query(..., min_length=1, max_length=120),
    limit: int = Query(15, ge=1, le=50),
    item_type: str | None = Query(None),
    ctx: AppContext = Depends(get_ctx),
):
    """Ranked autocomplete across all known market names."""
    results = ctx.itemdb.search(q, limit=limit, item_type=item_type)
    return {"query": q, "results": [_variant_payload(v, ctx) for v in results]}


@router.get("/items/detail")
async def item_detail(
    name: str = Query(..., description="Exact market_hash_name"),
    ctx: AppContext = Depends(get_ctx),
):
    """Catalog metadata for one market name (no live listings)."""
    v = ctx.itemdb.lookup(name)
    if not v:
        raise HTTPException(404, detail=f"Unknown item: {name}")
    return _variant_payload(v, ctx)


@router.get("/items/types")
async def item_types(ctx: AppContext = Depends(get_ctx)):
    """Item type counts, e.g. for filter dropdowns."""
    return ctx.itemdb.stats()["by_type"]
