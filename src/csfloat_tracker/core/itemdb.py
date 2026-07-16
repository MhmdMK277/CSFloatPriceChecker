"""Item database: load, refresh, search and lookup for all CS2 items.

The database is a JSON file of compact base items produced by
:mod:`schema_parser`. A copy generated at build time ships with the repo so
the tool works offline; at runtime a fresher copy is written to the app data
directory and auto-refreshed from CSFloat when older than ``max_age_days``.
"""

from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .client import CSFloatClient
from .errors import CSFloatError
from .models import ItemVariant
from .paths import bundled_itemdb_path, itemdb_path
from .schema_parser import BaseItem, collections_map, parse_schema, rarities_map
from .search import VariantSearch

logger = logging.getLogger(__name__)

DB_FORMAT_VERSION = 2


class ItemDatabase:
    def __init__(self, path: Path | None = None, *, max_age_days: int = 7) -> None:
        self.path = path or itemdb_path()
        self.max_age_days = max_age_days
        self.generated_at: datetime | None = None
        self.items: list[BaseItem] = []
        self.collections: dict[str, str] = {}
        self.rarities: dict[int, str] = {}
        self._search: VariantSearch | None = None
        self._variants: dict[str, ItemVariant] = {}
        self._refresh_lock = asyncio.Lock()

    # ------------------------------------------------------------------
    # Loading & persistence
    # ------------------------------------------------------------------

    def load(self) -> bool:
        """Load from the runtime path, falling back to the bundled baseline."""
        for candidate in (self.path, bundled_itemdb_path()):
            if candidate.exists():
                try:
                    self._load_file(candidate)
                    logger.info(
                        "Item database loaded from %s (%d base items, %d names)",
                        candidate, len(self.items), len(self._variants),
                    )
                    return True
                except (ValueError, KeyError, OSError) as exc:
                    logger.warning("Failed to load item DB %s: %s", candidate, exc)
        return False

    def _load_file(self, path: Path) -> None:
        with open(path, encoding="utf-8") as fh:
            payload = json.load(fh)
        if payload.get("format") != DB_FORMAT_VERSION:
            raise ValueError(f"unsupported item DB format: {payload.get('format')}")
        self.generated_at = datetime.fromisoformat(payload["generated_at"])
        self.collections = payload.get("collections") or {}
        self.rarities = {int(k): v for k, v in (payload.get("rarities") or {}).items()}
        self.items = [BaseItem.from_json(d) for d in payload["items"]]
        self._build_index()

    def save(self) -> None:
        payload = {
            "format": DB_FORMAT_VERSION,
            "generated_at": (self.generated_at or datetime.now(UTC)).isoformat(),
            "source": "csfloat_schema",
            "collections": self.collections,
            "rarities": self.rarities,
            "items": [i.to_json() for i in self.items],
        }
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(payload, fh, ensure_ascii=False, separators=(",", ":"))
        tmp.replace(self.path)

    def _build_index(self) -> None:
        self._variants = {}
        for base in self.items:
            for v in base.variants():
                existing = self._variants.get(v.market_hash_name)
                if existing is None:
                    self._variants[v.market_hash_name] = v
                else:
                    # Doppler phases share one market name; keep the cheapest
                    # phase as the conservative reference price.
                    old, new = existing.reference_price_cents, v.reference_price_cents
                    if new is not None and (old is None or new < old):
                        self._variants[v.market_hash_name] = v
        self._search = VariantSearch(self._variants)

    # ------------------------------------------------------------------
    # Refresh
    # ------------------------------------------------------------------

    def is_stale(self) -> bool:
        if self.generated_at is None:
            return True
        age = datetime.now(UTC) - self.generated_at
        return age > timedelta(days=self.max_age_days)

    async def refresh(self, client: CSFloatClient) -> dict[str, Any]:
        """Fetch the latest schema and rebuild the database."""
        async with self._refresh_lock:
            logger.info("Refreshing item database from CSFloat schema...")
            schema = await client.get_schema()
            if not schema.get("weapons"):
                raise CSFloatError("CSFloat schema response was empty; keeping existing database.")
            self.items = parse_schema(schema)
            self.collections = collections_map(schema)
            self.rarities = rarities_map(schema)
            self.generated_at = datetime.now(UTC)
            self._build_index()
            self.save()
            stats = self.stats()
            logger.info("Item database refreshed: %s", stats)
            return stats

    async def ensure_fresh(self, client: CSFloatClient) -> None:
        """Refresh in place if stale; log-and-continue on failure (offline OK)."""
        if not self.is_stale():
            return
        try:
            await self.refresh(client)
        except Exception as exc:
            logger.warning("Item DB auto-refresh failed (continuing with cached data): %s", exc)

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    def search(self, query: str, limit: int = 15, item_type: str | None = None) -> list[ItemVariant]:
        if not self._search:
            return []
        return self._search.query(query, limit=limit, item_type=item_type)

    def lookup(self, market_hash_name: str) -> ItemVariant | None:
        return self._variants.get(market_hash_name)

    def all_names(self) -> list[str]:
        return list(self._variants.keys())

    def stats(self) -> dict[str, Any]:
        by_type: dict[str, int] = {}
        for base in self.items:
            by_type[base.item_type] = by_type.get(base.item_type, 0) + 1
        return {
            "generated_at": self.generated_at.isoformat() if self.generated_at else None,
            "stale": self.is_stale(),
            "base_items": len(self.items),
            "market_names": len(self._variants),
            "by_type": dict(sorted(by_type.items(), key=lambda kv: -kv[1])),
        }
