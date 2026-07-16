"""Pydantic models for CSFloat data, normalized for internal use.

CSFloat's listing payloads are deeply nested and evolve over time, so
parsing is tolerant: unknown fields are ignored and missing ones default
to ``None``. Prices stay in integer cents internally; only the UI renders
dollars.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

CSFLOAT_ITEM_URL = "https://csfloat.com/item/{id}"


class ListingSticker(BaseModel):
    name: str | None = None
    slot: int | None = None
    wear: float | None = None
    icon_url: str | None = None
    reference_price_cents: int | None = None

    @classmethod
    def from_api(cls, raw: dict[str, Any]) -> ListingSticker:
        ref = raw.get("reference") or {}
        return cls(
            name=raw.get("name"),
            slot=raw.get("slot"),
            wear=raw.get("wear"),
            icon_url=raw.get("icon_url"),
            reference_price_cents=ref.get("price"),
        )


class Seller(BaseModel):
    username: str | None = None
    avatar: str | None = None
    total_trades: int | None = None
    verified_trades: int | None = None
    median_trade_time_minutes: int | None = None

    @classmethod
    def from_api(cls, raw: dict[str, Any] | None) -> Seller | None:
        if not raw:
            return None
        stats = raw.get("statistics") or {}
        return cls(
            username=raw.get("username"),
            avatar=raw.get("avatar"),
            total_trades=stats.get("total_trades"),
            verified_trades=stats.get("total_verified_trades"),
            median_trade_time_minutes=stats.get("median_trade_time"),
        )


class Listing(BaseModel):
    """A normalized CSFloat market listing."""

    id: str
    created_at: datetime | None = None
    type: str = "buy_now"  # buy_now | auction
    price_cents: int = 0
    market_hash_name: str = ""
    float_value: float | None = None
    paint_seed: int | None = None
    paint_index: int | None = None
    def_index: int | None = None
    wear_name: str | None = None
    is_stattrak: bool = False
    is_souvenir: bool = False
    rarity: int | None = None
    collection: str | None = None
    icon_url: str | None = None
    inspect_link: str | None = None
    stickers: list[ListingSticker] = Field(default_factory=list)
    seller: Seller | None = None
    watchers: int | None = None
    scm_price_cents: int | None = None  # Steam Community Market reference
    reference_price_cents: int | None = None  # CSFloat predicted/base price

    @property
    def price_usd(self) -> float:
        return round(self.price_cents / 100, 2)

    @property
    def url(self) -> str:
        return CSFLOAT_ITEM_URL.format(id=self.id)

    @classmethod
    def from_api(cls, raw: dict[str, Any]) -> Listing:
        item = raw.get("item") or {}
        scm = item.get("scm") or {}
        reference = raw.get("reference") or {}
        return cls(
            id=str(raw.get("id", "")),
            created_at=raw.get("created_at"),
            type=raw.get("type") or ("auction" if raw.get("auction_details") else "buy_now"),
            price_cents=int(raw.get("price") or 0),
            market_hash_name=item.get("market_hash_name") or "",
            float_value=item.get("float_value"),
            paint_seed=item.get("paint_seed"),
            paint_index=item.get("paint_index"),
            def_index=item.get("def_index"),
            wear_name=item.get("wear_name"),
            is_stattrak=bool(item.get("is_stattrak")),
            is_souvenir=bool(item.get("is_souvenir")),
            rarity=item.get("rarity"),
            collection=item.get("collection"),
            icon_url=item.get("icon_url"),
            inspect_link=item.get("inspect_link"),
            stickers=[ListingSticker.from_api(s) for s in item.get("stickers") or []],
            seller=Seller.from_api(raw.get("seller")),
            watchers=raw.get("watchers"),
            scm_price_cents=scm.get("price"),
            reference_price_cents=reference.get("base_price") or reference.get("predicted_price"),
        )

    def to_public(self) -> dict[str, Any]:
        """Serializable dict for our REST API and CLI."""
        data = self.model_dump(mode="json")
        data["price_usd"] = self.price_usd
        data["url"] = self.url
        return data


class ItemVariant(BaseModel):
    """One purchasable market name expanded from a base item.

    e.g. base "AK-47 | X-Ray" produces variants like
    "Souvenir AK-47 | X-Ray (Field-Tested)".
    """

    market_hash_name: str
    base_name: str
    item_type: str  # skin | knife | glove | sticker | patch | charm | case | ...
    wear: str | None = None  # FN/MW/FT/WW/BS
    category: str = "normal"  # normal | stattrak | souvenir
    def_index: int | None = None
    paint_index: int | None = None
    rarity: int | None = None
    collections: list[str] = Field(default_factory=list)
    min_float: float | None = None
    max_float: float | None = None
    phase: str | None = None  # Doppler phase/gem when this name maps to one paint
    image: str | None = None
    reference_price_cents: int | None = None
    reference_volume: int | None = None
