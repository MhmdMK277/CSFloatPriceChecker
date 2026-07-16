"""Convert the CSFloat ``/api/v1/schema`` payload into our item database.

The schema groups everything by category. Weapons carry ``paints`` with
float ranges and per-wear reference prices; other categories are flat maps
of ``market_hash_name``. We store one compact record per *base item* and
expand purchasable variants (wear x StatTrak/Souvenir) on load, which keeps
the shipped JSON small while the in-memory name index covers all ~26k
market names.
"""

from __future__ import annotations

import re
from collections.abc import Iterator
from dataclasses import asdict, dataclass, field
from typing import Any

from .models import ItemVariant
from .wears import WEARS, wears_in_range

# Steam CDN prefix stripped from stored image URLs to shrink the database file.
IMAGE_PREFIX = "https://community.akamai.steamstatic.com/economy/image/"

# Doppler-style phases are separate paints in the schema ("Doppler (Phase 2)",
# "Gamma Doppler (Emerald)") but share one market_hash_name without the phase.
PHASE_RE = re.compile(r"^(?P<base>.+) \((?P<phase>Phase [1-4]|Ruby|Sapphire|Black Pearl|Emerald)\)$")

STATTRAK = "StatTrak™ "  # "StatTrak™ "
STAR = "★ "  # "★ "


def _compact_image(url: str | None) -> str | None:
    if url and url.startswith(IMAGE_PREFIX):
        return url[len(IMAGE_PREFIX) :]
    return url


def expand_image(compact: str | None) -> str | None:
    if compact and not compact.startswith("http"):
        return IMAGE_PREFIX + compact
    return compact


@dataclass
class BaseItem:
    """One catalog entry before wear/category expansion."""

    base_name: str
    item_type: str  # skin | knife | glove | sticker | patch | charm | case | agent | music_kit | collectible | highlight
    def_index: int | None = None
    paint_index: int | None = None
    rarity: int | None = None
    collections: list[str] = field(default_factory=list)
    min_float: float | None = None
    max_float: float | None = None
    has_stattrak: bool = False
    has_souvenir: bool = False
    phase: str | None = None  # Doppler phase / gem (Phase 1-4, Ruby, Sapphire, ...)
    image: str | None = None
    # Reference prices in cents: wearable items use 5-element [FN..BS] lists
    # keyed by category; flat items use {"normal": int}.
    prices: dict[str, list[int | None] | int | None] = field(default_factory=dict)
    volumes: dict[str, list[int | None]] = field(default_factory=dict)

    def to_json(self) -> dict[str, Any]:
        # Drop only true empties; 0 is meaningful (vanilla knives have paint_index 0).
        d = asdict(self)
        return {
            k: v for k, v in d.items()
            if v is not None and v is not False and v != [] and v != {}
        }

    @classmethod
    def from_json(cls, d: dict[str, Any]) -> BaseItem:
        return cls(**{k: d.get(k, v) for k, v in _DEFAULTS.items()})

    # ------------------------------------------------------------------

    def variants(self) -> Iterator[ItemVariant]:
        """Yield every purchasable market_hash_name for this base item."""
        common = dict(
            base_name=self.base_name,
            item_type=self.item_type,
            def_index=self.def_index,
            paint_index=self.paint_index,
            rarity=self.rarity,
            collections=self.collections,
            min_float=self.min_float,
            max_float=self.max_float,
            phase=self.phase,
            image=self.image,
        )

        if self.item_type in ("skin", "knife", "glove"):
            is_vanilla = self.paint_index == 0
            wear_list = (
                [None]
                if is_vanilla
                else wears_in_range(self.min_float or 0.0, self.max_float or 1.0)
            )
            categories = ["normal"]
            if self.has_stattrak:
                categories.append("stattrak")
            if self.has_souvenir:
                categories.append("souvenir")

            for category in categories:
                for wear in wear_list:
                    name = self._market_name(category, wear.name if wear else None)
                    price, volume = self._ref_price(category, wear)
                    yield ItemVariant(
                        market_hash_name=name,
                        wear=wear.abbr if wear else None,
                        category=category,
                        reference_price_cents=price,
                        reference_volume=volume,
                        **common,
                    )
        elif self.item_type == "music_kit":
            yield ItemVariant(
                market_hash_name=self.base_name,
                reference_price_cents=self._flat_price("normal"),
                **common,
            )
            if self.has_stattrak:
                yield ItemVariant(
                    market_hash_name=STATTRAK + self.base_name,
                    category="stattrak",
                    reference_price_cents=self._flat_price("stattrak"),
                    **common,
                )
        else:
            yield ItemVariant(
                market_hash_name=self.base_name,
                reference_price_cents=self._flat_price("normal"),
                **common,
            )

    def _market_name(self, category: str, wear_name: str | None) -> str:
        name = self.base_name
        if category == "stattrak":
            if self.item_type in ("knife", "glove"):
                # "★ StatTrak™ Karambit | Doppler"
                name = STAR + STATTRAK + name.removeprefix(STAR)
            else:
                name = STATTRAK + name
        elif category == "souvenir":
            name = "Souvenir " + name
        if wear_name:
            name = f"{name} ({wear_name})"
        return name

    def _ref_price(self, category: str, wear) -> tuple[int | None, int | None]:
        prices = self.prices.get(category)
        volumes = self.volumes.get(category)
        if wear is None or not isinstance(prices, list):
            return None, None
        idx = next((i for i, w in enumerate(WEARS) if w.abbr == wear.abbr), None)
        if idx is None or idx >= len(prices):
            return None, None
        vol = volumes[idx] if isinstance(volumes, list) and idx < len(volumes) else None
        return prices[idx], vol

    def _flat_price(self, category: str) -> int | None:
        p = self.prices.get(category)
        return p if isinstance(p, int) else None


_DEFAULTS = {
    "base_name": "",
    "item_type": "",
    "def_index": None,
    "paint_index": None,
    "rarity": None,
    "collections": [],
    "min_float": None,
    "max_float": None,
    "has_stattrak": False,
    "has_souvenir": False,
    "phase": None,
    "image": None,
    "prices": {},
    "volumes": {},
}


# ----------------------------------------------------------------------
# Schema parsing
# ----------------------------------------------------------------------

def parse_schema(schema: dict[str, Any]) -> list[BaseItem]:
    """Flatten a CSFloat schema payload into base items."""
    items: list[BaseItem] = []

    for def_index, weapon in (schema.get("weapons") or {}).items():
        wtype = weapon.get("type", "Weapons")
        item_type = {"Weapons": "skin", "Knives": "knife", "Gloves": "glove"}.get(wtype, "skin")
        weapon_name = weapon.get("name", "")
        display_weapon = (STAR + weapon_name) if item_type in ("knife", "glove") else weapon_name

        for paint_index, paint in (weapon.get("paints") or {}).items():
            is_vanilla = int(paint_index) == 0
            paint_name = paint.get("name") or ""
            phase = None
            m = PHASE_RE.match(paint_name)
            if m:
                paint_name, phase = m.group("base"), m.group("phase")
            base_name = display_weapon if is_vanilla else f"{display_weapon} | {paint_name}"
            prices: dict[str, Any] = {}
            volumes: dict[str, Any] = {}
            if "normal_prices" in paint:
                prices["normal"] = paint["normal_prices"]
                volumes["normal"] = paint.get("normal_volume")
            if paint.get("stattrak"):
                prices["stattrak"] = paint.get("stattrak_prices")
                volumes["stattrak"] = paint.get("stattrak_volume")
            items.append(
                BaseItem(
                    base_name=base_name,
                    item_type=item_type,
                    def_index=int(def_index),
                    paint_index=int(paint_index),
                    rarity=paint.get("rarity"),
                    collections=paint.get("collections") or [],
                    min_float=paint.get("min"),
                    max_float=paint.get("max"),
                    has_stattrak=bool(paint.get("stattrak")) or (item_type == "knife" and is_vanilla),
                    has_souvenir=bool(paint.get("souvenir")),
                    phase=phase,
                    image=_compact_image(paint.get("image")),
                    prices=prices,
                    volumes={k: v for k, v in volumes.items() if v},
                )
            )

    def flat(section: str, item_type: str) -> None:
        for key, entry in (schema.get(section) or {}).items():
            name = entry.get("market_hash_name")
            if not name:
                continue
            price = entry.get("price")
            items.append(
                BaseItem(
                    base_name=name,
                    item_type=item_type,
                    def_index=int(key) if str(key).isdigit() else None,
                    rarity=entry.get("rarity"),
                    image=_compact_image(entry.get("image")),
                    prices={"normal": price} if isinstance(price, int) else {},
                )
            )

    # Stickers include patches, flagged with is_patch.
    for key, entry in (schema.get("stickers") or {}).items():
        name = entry.get("market_hash_name")
        if not name:
            continue
        items.append(
            BaseItem(
                base_name=name,
                item_type="patch" if entry.get("is_patch") else "sticker",
                def_index=int(key) if str(key).isdigit() else None,
            )
        )

    flat("keychains", "charm")
    flat("containers", "case")
    flat("collectibles", "collectible")
    flat("agents", "agent")
    flat("highlight_reels", "highlight")

    for key, entry in (schema.get("music_kits") or {}).items():
        name = entry.get("market_hash_name")
        if not name:
            continue
        prices: dict[str, Any] = {}
        if isinstance(entry.get("normal_price"), int):
            prices["normal"] = entry["normal_price"]
        if isinstance(entry.get("stattrak_price"), int):
            prices["stattrak"] = entry["stattrak_price"]
        items.append(
            BaseItem(
                base_name=name,
                item_type="music_kit",
                def_index=int(key) if str(key).isdigit() else None,
                rarity=entry.get("rarity"),
                image=_compact_image(entry.get("image")),
                has_stattrak="stattrak" in prices,
                prices=prices,
            )
        )

    items.extend(load_graffiti_supplement())
    return items


def load_graffiti_supplement() -> list[BaseItem]:
    """Graffiti isn't in CSFloat's schema; a static name list ships with us.

    Sprays haven't been added to CS2 in years, so a static supplement stays
    accurate. Returns an empty list when the file is absent.
    """
    import json
    from pathlib import Path

    candidates = [
        Path(__file__).resolve().parent.parent / "data" / "graffiti.json",
        Path(__file__).resolve().parents[3] / "data" / "graffiti.json",
    ]
    for path in candidates:
        if path.exists():
            with open(path, encoding="utf-8") as fh:
                names = json.load(fh)
            return [BaseItem(base_name=n, item_type="graffiti") for n in names]
    return []


def collections_map(schema: dict[str, Any]) -> dict[str, str]:
    """Map collection key -> display name (e.g. set_cache -> The Cache Collection)."""
    return {c["key"]: c["name"] for c in schema.get("collections") or [] if c.get("key")}


def rarities_map(schema: dict[str, Any]) -> dict[int, str]:
    return {r["value"]: r["name"] for r in schema.get("rarities") or [] if "value" in r}
