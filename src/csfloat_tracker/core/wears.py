"""CS2 wear tiers and float-range helpers."""

from __future__ import annotations

from typing import NamedTuple


class Wear(NamedTuple):
    name: str
    abbr: str
    lo: float  # inclusive
    hi: float  # exclusive (except BS, whose upper bound 1.0 is inclusive)


WEARS: tuple[Wear, ...] = (
    Wear("Factory New", "FN", 0.00, 0.07),
    Wear("Minimal Wear", "MW", 0.07, 0.15),
    Wear("Field-Tested", "FT", 0.15, 0.38),
    Wear("Well-Worn", "WW", 0.38, 0.45),
    Wear("Battle-Scarred", "BS", 0.45, 1.00),
)

WEAR_BY_ABBR = {w.abbr: w for w in WEARS}
WEAR_BY_NAME = {w.name: w for w in WEARS}


def wear_for_float(value: float) -> Wear | None:
    """Return the wear tier a float value falls into."""
    if not 0.0 <= value <= 1.0:
        return None
    for w in WEARS:
        if value < w.hi:
            return w
    return WEARS[-1]  # value == 1.0


def wears_in_range(min_float: float, max_float: float) -> list[Wear]:
    """Return the wear tiers a paint's [min_float, max_float] range can produce."""
    out = []
    for w in WEARS:
        if min_float < w.hi and max_float > w.lo:
            out.append(w)
    # Edge case: paints capped exactly at a boundary (e.g. max 0.07 -> FN only)
    if not out and 0.0 <= min_float <= max_float <= 1.0:
        found = wear_for_float(min_float)
        if found:
            out.append(found)
    return out
