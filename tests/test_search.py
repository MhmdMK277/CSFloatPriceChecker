from csfloat_tracker.core.search import SearchIndex

NAMES = [
    "AK-47 | Redline (Field-Tested)",
    "AK-47 | Redline (Minimal Wear)",
    "AK-47 | Asiimov (Field-Tested)",
    "M4A4 | Asiimov (Field-Tested)",
    "AWP | Asiimov (Battle-Scarred)",
    "★ Karambit | Doppler (Factory New)",
    "★ Karambit | Fade (Factory New)",
    "Sticker | Crown (Foil)",
    "Desert Eagle | Blaze (Factory New)",
]


def test_prefix_beats_substring():
    idx = SearchIndex(NAMES)
    results = idx.query("ak-47")
    assert results[0].startswith("AK-47")


def test_word_prefix_match():
    idx = SearchIndex(NAMES)
    results = idx.query("kara")
    assert any("Karambit" in r for r in results[:2])


def test_multi_token_substring():
    idx = SearchIndex(NAMES)
    results = idx.query("awp asiimov")
    assert results[0] == "AWP | Asiimov (Battle-Scarred)"


def test_fuzzy_typo():
    idx = SearchIndex(NAMES)
    results = idx.query("asimov")  # missing an i
    assert any("Asiimov" in r for r in results)


def test_empty_query():
    idx = SearchIndex(NAMES)
    assert idx.query("") == []
    assert idx.query("   ") == []


def test_limit_respected():
    idx = SearchIndex(NAMES)
    assert len(idx.query("a", limit=3)) <= 3
