from csfloat_tracker.core.wears import WEARS, wear_for_float, wears_in_range


def test_wear_for_float_boundaries():
    assert wear_for_float(0.0).abbr == "FN"
    assert wear_for_float(0.06999).abbr == "FN"
    assert wear_for_float(0.07).abbr == "MW"
    assert wear_for_float(0.15).abbr == "FT"
    assert wear_for_float(0.379999).abbr == "FT"
    assert wear_for_float(0.38).abbr == "WW"
    assert wear_for_float(0.45).abbr == "BS"
    assert wear_for_float(1.0).abbr == "BS"


def test_wear_for_float_out_of_range():
    assert wear_for_float(-0.1) is None
    assert wear_for_float(1.1) is None


def test_wears_in_range_full():
    assert [w.abbr for w in wears_in_range(0.0, 1.0)] == ["FN", "MW", "FT", "WW", "BS"]


def test_wears_in_range_partial():
    # Redline: 0.10 - 0.70 -> MW..BS, no FN
    assert [w.abbr for w in wears_in_range(0.10, 0.70)] == ["MW", "FT", "WW", "BS"]
    # Doppler-like: 0.0 - 0.08 -> FN + MW
    assert [w.abbr for w in wears_in_range(0.0, 0.08)] == ["FN", "MW"]


def test_wears_in_range_degenerate():
    # A cap exactly at a boundary still yields at least one wear
    assert len(wears_in_range(0.07, 0.07)) >= 1


def test_wear_table_is_contiguous():
    import itertools

    for a, b in itertools.pairwise(WEARS):
        assert a.hi == b.lo
