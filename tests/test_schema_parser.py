from csfloat_tracker.core.schema_parser import (
    BaseItem,
    collections_map,
    parse_schema,
    rarities_map,
)


def expand_names(items: list[BaseItem]) -> dict[str, object]:
    return {v.market_hash_name: v for base in items for v in base.variants()}


def test_parse_counts(mini_schema):
    items = parse_schema(mini_schema)
    by_type = {}
    for i in items:
        by_type[i.item_type] = by_type.get(i.item_type, 0) + 1
    assert by_type["skin"] == 1
    assert by_type["knife"] == 3  # vanilla + 2 doppler phases
    assert by_type["glove"] == 1
    assert by_type["sticker"] == 1
    assert by_type["patch"] == 1
    assert by_type["music_kit"] == 1


def test_skin_expansion(mini_schema):
    names = expand_names(parse_schema(mini_schema))
    # Redline 0.10-0.70 => MW..BS, normal + stattrak, no souvenir
    assert "AK-47 | Redline (Minimal Wear)" in names
    assert "AK-47 | Redline (Battle-Scarred)" in names
    assert "AK-47 | Redline (Factory New)" not in names
    assert "StatTrak™ AK-47 | Redline (Field-Tested)" in names
    assert "Souvenir AK-47 | Redline (Field-Tested)" not in names

    ft = names["AK-47 | Redline (Field-Tested)"]
    assert ft.reference_price_cents == 2894
    assert ft.reference_volume == 90
    assert ft.wear == "FT"

    st = names["StatTrak™ AK-47 | Redline (Field-Tested)"]
    assert st.reference_price_cents == 6284
    assert st.category == "stattrak"


def test_vanilla_knife(mini_schema):
    names = expand_names(parse_schema(mini_schema))
    assert "★ Karambit" in names
    assert "★ StatTrak™ Karambit" in names
    # Vanilla has no wear-suffixed variants
    assert "★ Karambit (Factory New)" not in names


def test_doppler_phase_merging(mini_schema):
    names = expand_names(parse_schema(mini_schema))
    # Phases collapse into one market name (no phase in the name)
    assert "★ Karambit | Doppler (Factory New)" in names
    assert "★ Karambit | Doppler (Phase 1) (Factory New)" not in names
    assert "★ StatTrak™ Karambit | Doppler (Factory New)" in names
    # Phase metadata is preserved on the variant
    items = parse_schema(mini_schema)
    phases = {i.phase for i in items if i.item_type == "knife"}
    assert "Phase 1" in phases and "Phase 2" in phases


def test_glove_expansion(mini_schema):
    names = expand_names(parse_schema(mini_schema))
    assert "★ Sport Gloves | Pandora's Box (Field-Tested)" in names
    assert "StatTrak™ ★ Sport Gloves | Pandora's Box (Field-Tested)" not in names
    assert "★ StatTrak™ Sport Gloves | Pandora's Box (Field-Tested)" not in names


def test_music_kit_stattrak(mini_schema):
    names = expand_names(parse_schema(mini_schema))
    assert "Music Kit | Test Artist, Test Song" in names
    assert "StatTrak™ Music Kit | Test Artist, Test Song" in names
    assert names["StatTrak™ Music Kit | Test Artist, Test Song"].reference_price_cents == 455


def test_flat_sections(mini_schema):
    names = expand_names(parse_schema(mini_schema))
    for expected in (
        "Sticker | Shooter",
        "Patch | Test Patch",
        "Charm | Lil' Ava",
        "CS:GO Weapon Case",
        "Test Pin",
        "Test Agent | SWAT",
        "Souvenir Charm | Test Highlight",
    ):
        assert expected in names
    assert names["Test Pin"].reference_price_cents == 1589


def test_json_roundtrip_preserves_paint_index_zero(mini_schema):
    items = parse_schema(mini_schema)
    vanilla = next(i for i in items if i.base_name == "★ Karambit")
    assert vanilla.paint_index == 0
    restored = BaseItem.from_json(vanilla.to_json())
    assert restored.paint_index == 0
    # Vanilla restored item must not expand into wear variants
    names = [v.market_hash_name for v in restored.variants()]
    assert names == ["★ Karambit", "★ StatTrak™ Karambit"]


def test_maps(mini_schema):
    assert collections_map(mini_schema) == {"set_test": "The Test Collection"}
    assert rarities_map(mini_schema) == {6: "Covert"}


def test_image_compaction(mini_schema):
    items = parse_schema(mini_schema)
    redline = next(i for i in items if "Redline" in i.base_name)
    assert redline.image == "abc123"  # prefix stripped
