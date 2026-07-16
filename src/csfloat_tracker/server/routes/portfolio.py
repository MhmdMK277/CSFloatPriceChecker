"""Portfolio tracking: buys, current value and P&L."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field

from ...core.stats import portfolio_summary
from ..deps import AppContext, get_ctx

router = APIRouter()


class PortfolioAdd(BaseModel):
    market_hash_name: str
    buy_price_cents: int = Field(..., ge=0)
    quantity: int = Field(1, ge=1)
    acquired_at: str | None = None
    note: str | None = Field(None, max_length=500)


@router.get("/portfolio")
async def get_portfolio(ctx: AppContext = Depends(get_ctx)):
    """All entries with P&L against CSFloat reference prices."""
    entries = await ctx.storage.list_portfolio()
    current: dict[str, int | None] = {}
    for e in entries:
        name = e["market_hash_name"]
        if name not in current:
            variant = ctx.itemdb.lookup(name)
            current[name] = variant.reference_price_cents if variant else None
    return portfolio_summary(entries, current)


@router.post("/portfolio", status_code=201)
async def add_entry(body: PortfolioAdd, ctx: AppContext = Depends(get_ctx)):
    return await ctx.storage.add_portfolio_entry(
        body.market_hash_name,
        body.buy_price_cents,
        quantity=body.quantity,
        acquired_at=body.acquired_at,
        note=body.note,
    )


@router.delete("/portfolio/{entry_id}")
async def delete_entry(entry_id: int, ctx: AppContext = Depends(get_ctx)):
    await ctx.storage.delete_portfolio_entry(entry_id)
    return {"ok": True}
