"""Shared fixtures: isolated data dir and a synthetic CSFloat schema."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def isolated_data_dir(tmp_path, monkeypatch):
    """Keep every test away from the real app-data directory."""
    monkeypatch.setenv("CSFLOAT_TRACKER_DATA", str(tmp_path / "appdata"))
    return tmp_path / "appdata"


@pytest.fixture
def mini_schema() -> dict:
    """A minimal but structurally faithful CSFloat schema payload."""
    return {
        "collections": [
            {"key": "set_test", "name": "The Test Collection", "has_souvenir": True},
        ],
        "rarities": [
            {"key": "ancient", "name": "Covert", "value": 6},
        ],
        "weapons": {
            "7": {
                "name": "AK-47",
                "type": "Weapons",
                "paints": {
                    "282": {
                        "index": 282,
                        "name": "Redline",
                        "min": 0.10,
                        "max": 0.70,
                        "rarity": 5,
                        "collections": ["set_test"],
                        "image": "https://community.akamai.steamstatic.com/economy/image/abc123",
                        "stattrak": True,
                        "normal_prices": [None, 3500, 2894, 2500, 2200],
                        "normal_volume": [0, 10, 90, 20, 15],
                        "stattrak_prices": [None, 8000, 6284, 5000, 4500],
                        "stattrak_volume": [0, 2, 12, 3, 2],
                    },
                },
            },
            "507": {
                "name": "Karambit",
                "type": "Knives",
                "paints": {
                    "0": {
                        "index": 0,
                        "name": "Vanilla",
                        "min": 0.06,
                        "max": 0.80,
                        "rarity": 6,
                        "collections": [],
                        "normal_prices": [0, 0, 0, 0, 0],
                        "normal_volume": [0, 0, 0, 0, 0],
                    },
                    "418": {
                        "index": 418,
                        "name": "Doppler (Phase 1)",
                        "min": 0.0,
                        "max": 0.08,
                        "rarity": 6,
                        "collections": [],
                        "stattrak": True,
                        "normal_prices": [120000, 110000, None, None, None],
                        "normal_volume": [5, 2, 0, 0, 0],
                        "stattrak_prices": [150000, None, None, None, None],
                        "stattrak_volume": [1, 0, 0, 0, 0],
                    },
                    "419": {
                        "index": 419,
                        "name": "Doppler (Phase 2)",
                        "min": 0.0,
                        "max": 0.08,
                        "rarity": 6,
                        "collections": [],
                        "stattrak": True,
                        "normal_prices": [100000, 90000, None, None, None],
                        "normal_volume": [4, 1, 0, 0, 0],
                        "stattrak_prices": [140000, None, None, None, None],
                        "stattrak_volume": [1, 0, 0, 0, 0],
                    },
                },
            },
            "5027": {
                "name": "Sport Gloves",
                "type": "Gloves",
                "paints": {
                    "10037": {
                        "index": 10037,
                        "name": "Pandora's Box",
                        "min": 0.06,
                        "max": 0.80,
                        "rarity": 6,
                        "collections": [],
                        "normal_prices": [None, 500000, 300000, 250000, 200000],
                        "normal_volume": [0, 1, 3, 2, 1],
                    },
                },
            },
        },
        "stickers": {
            "1": {"market_hash_name": "Sticker | Shooter"},
            "2": {"market_hash_name": "Patch | Test Patch", "is_patch": True},
        },
        "keychains": {"1": {"market_hash_name": "Charm | Lil' Ava"}},
        "containers": {"4001": {"market_hash_name": "CS:GO Weapon Case"}},
        "collectibles": {"4682": {"market_hash_name": "Test Pin", "rarity": 6, "price": 1589}},
        "agents": {"4613": {"market_hash_name": "Test Agent | SWAT", "rarity": 5, "price": 3355, "faction": "ct"}},
        "custom_stickers": {},
        "music_kits": {
            "10": {
                "market_hash_name": "Music Kit | Test Artist, Test Song",
                "rarity": 3,
                "normal_price": 174,
                "stattrak_price": 455,
            },
        },
        "highlight_reels": {
            "1": {
                "name": "Test Highlight",
                "keychain_index": 36,
                "market_hash_name": "Souvenir Charm | Test Highlight",
            },
        },
    }


def make_listing(
    listing_id: str = "123456",
    price: int = 2894,
    float_value: float = 0.23,
    name: str = "AK-47 | Redline (Field-Tested)",
    **overrides,
) -> dict:
    """Raw CSFloat listing payload for tests."""
    raw = {
        "id": listing_id,
        "created_at": "2026-07-16T10:00:00Z",
        "type": "buy_now",
        "price": price,
        "state": "listed",
        "watchers": 3,
        "seller": {
            "username": "trader1",
            "avatar": "https://example.com/a.jpg",
            "statistics": {"total_trades": 100, "total_verified_trades": 98, "median_trade_time": 22},
        },
        "reference": {"base_price": 3100, "predicted_price": 3050},
        "item": {
            "asset_id": "999",
            "def_index": 7,
            "paint_index": 282,
            "paint_seed": 555,
            "float_value": float_value,
            "market_hash_name": name,
            "wear_name": "Field-Tested",
            "is_stattrak": False,
            "is_souvenir": False,
            "rarity": 5,
            "collection": "The Test Collection",
            "icon_url": "econ/default_generated/ak47_redline",
            "inspect_link": "steam://rungame/730/…",
            "stickers": [
                {"stickerId": 4, "slot": 0, "name": "Sticker | Shooter", "reference": {"price": 50}},
            ],
            "scm": {"price": 3000, "volume": 120},
        },
    }
    raw.update(overrides)
    return raw
