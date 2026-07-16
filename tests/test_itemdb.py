from pathlib import Path

import httpx
import pytest
import respx

from csfloat_tracker.core.client import BASE_URL, CSFloatClient
from csfloat_tracker.core.itemdb import ItemDatabase
from csfloat_tracker.core.schema_parser import collections_map, parse_schema, rarities_map


@pytest.fixture
def db(tmp_path, mini_schema) -> ItemDatabase:
    from datetime import UTC, datetime

    database = ItemDatabase(tmp_path / "items.json")
    database.items = parse_schema(mini_schema)
    database.collections = collections_map(mini_schema)
    database.rarities = rarities_map(mini_schema)
    database.generated_at = datetime.now(UTC)
    database._build_index()
    database.save()
    return database


def test_save_load_roundtrip(db, tmp_path):
    fresh = ItemDatabase(tmp_path / "items.json")
    assert fresh.load() is True
    assert fresh.lookup("AK-47 | Redline (Field-Tested)") is not None
    assert fresh.lookup("★ Karambit").paint_index == 0
    assert fresh.collections == {"set_test": "The Test Collection"}
    assert not fresh.is_stale()


def test_missing_db_load_fails(tmp_path, monkeypatch):
    # Point the bundled path somewhere empty as well
    monkeypatch.setattr(
        "csfloat_tracker.core.itemdb.bundled_itemdb_path",
        lambda: Path(tmp_path / "nope.json"),
    )
    fresh = ItemDatabase(tmp_path / "missing.json")
    assert fresh.load() is False


def test_doppler_reference_uses_cheapest_phase(db):
    v = db.lookup("★ Karambit | Doppler (Factory New)")
    # Phase 2 (100000) is cheaper than Phase 1 (120000)
    assert v.reference_price_cents == 100000


def test_staleness(db):
    from datetime import UTC, datetime, timedelta

    db.generated_at = datetime.now(UTC) - timedelta(days=8)
    assert db.is_stale() is True
    db.generated_at = datetime.now(UTC) - timedelta(days=2)
    assert db.is_stale() is False
    db.generated_at = None
    assert db.is_stale() is True


def test_search_filters_by_type(db):
    results = db.search("test", item_type="music_kit", limit=5)
    assert results
    assert all(v.item_type == "music_kit" for v in results)


def test_stats(db):
    stats = db.stats()
    assert stats["market_names"] > 10
    assert stats["by_type"]["knife"] == 3


@respx.mock
async def test_refresh_from_schema(tmp_path, mini_schema):
    respx.get(f"{BASE_URL}/schema").mock(return_value=httpx.Response(200, json=mini_schema))
    database = ItemDatabase(tmp_path / "items.json")
    async with CSFloatClient() as client:
        stats = await database.refresh(client)
    assert stats["base_items"] > 0
    assert database.lookup("AK-47 | Redline (Field-Tested)") is not None
    assert (tmp_path / "items.json").exists()


@respx.mock
async def test_refresh_rejects_empty_schema(db):
    from csfloat_tracker.core.errors import CSFloatError

    respx.get(f"{BASE_URL}/schema").mock(return_value=httpx.Response(200, json={}))
    before = len(db.items)
    async with CSFloatClient() as client:
        with pytest.raises(CSFloatError):
            await db.refresh(client)
    assert len(db.items) == before


@respx.mock
async def test_ensure_fresh_swallows_failures(db):
    from datetime import UTC, datetime, timedelta

    respx.get(f"{BASE_URL}/schema").mock(return_value=httpx.Response(500))
    db.generated_at = datetime.now(UTC) - timedelta(days=30)
    async with CSFloatClient(max_retries=0) as client:
        await db.ensure_fresh(client)  # must not raise; cached data stays usable
    assert db.lookup("AK-47 | Redline (Field-Tested)") is not None
