"""Deal finder (sniper mode) results and configuration."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from ..deps import AppContext, get_ctx

router = APIRouter()

DEFAULT_CONFIG = {
    "enabled": False,
    "min_discount_pct": 15.0,
    "min_price_cents": 500,      # ignore penny items where % means nothing
    "interval_seconds": 120,
    "max_price_cents": None,     # optional budget cap
}


class DealConfig(BaseModel):
    enabled: bool = False
    min_discount_pct: float = Field(15.0, ge=1, le=90)
    min_price_cents: int = Field(500, ge=0)
    interval_seconds: int = Field(120, ge=60, le=3600)
    max_price_cents: int | None = Field(None, ge=0)


@router.get("/deals")
async def list_deals(limit: int = Query(100, ge=1, le=500), ctx: AppContext = Depends(get_ctx)):
    return {"deals": await ctx.storage.list_deals(limit)}


@router.get("/deals/config")
async def get_config(ctx: AppContext = Depends(get_ctx)):
    stored = await ctx.storage.get_setting("deal_finder", {})
    return {**DEFAULT_CONFIG, **stored}


@router.put("/deals/config")
async def set_config(body: DealConfig, ctx: AppContext = Depends(get_ctx)):
    await ctx.storage.set_setting("deal_finder", body.model_dump())
    return body.model_dump()
