"""Generate the baseline item database shipped with the repo.

Usage::

    python scripts/generate_itemdb.py [schema.json]

Fetches the CSFloat schema (or reads a local copy) and writes
``data/cs2_items.json``. Run before releases to keep the offline baseline
fresh.
"""

from __future__ import annotations

import asyncio
import json
import sys
from datetime import UTC, datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from csfloat_tracker.core.itemdb import DB_FORMAT_VERSION  # noqa: E402
from csfloat_tracker.core.schema_parser import (  # noqa: E402
    collections_map,
    parse_schema,
    rarities_map,
)


async def fetch_schema() -> dict:
    from csfloat_tracker.core.client import CSFloatClient

    async with CSFloatClient() as client:
        return await client.get_schema()


def main() -> None:
    if len(sys.argv) > 1:
        schema = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
        print(f"Loaded schema from {sys.argv[1]}")
    else:
        schema = asyncio.run(fetch_schema())
        print("Fetched schema from CSFloat")

    items = parse_schema(schema)
    payload = {
        "format": DB_FORMAT_VERSION,
        "generated_at": datetime.now(UTC).isoformat(),
        "source": "csfloat_schema",
        "collections": collections_map(schema),
        "rarities": rarities_map(schema),
        "items": [i.to_json() for i in items],
    }

    out = ROOT / "data" / "cs2_items.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(payload, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")

    total_names = sum(1 for base in items for _ in base.variants())
    by_type: dict[str, int] = {}
    for base in items:
        by_type[base.item_type] = by_type.get(base.item_type, 0) + 1
    print(f"Wrote {out} ({out.stat().st_size / 1e6:.1f} MB)")
    print(f"Base items: {len(items)}, expanded market names: {total_names}")
    print("By type:", dict(sorted(by_type.items(), key=lambda kv: -kv[1])))


if __name__ == "__main__":
    main()
