"""Ranked autocomplete over ~26k market names.

Ranking tiers (highest wins), with fuzzy matching as a fallback so typos
like "asimov" still find "Asiimov":

1. full-string prefix match
2. word-boundary prefix match ("kara" -> "★ Karambit ...")
3. all query tokens appear as substrings
4. RapidFuzz partial ratio above a threshold
"""

from __future__ import annotations

import re
from typing import Any

from rapidfuzz import fuzz, process

_WORD_SPLIT = re.compile(r"[^a-z0-9™★]+")


def _norm(s: str) -> str:
    return s.lower().strip()


class SearchIndex:
    def __init__(self, names: list[str]) -> None:
        self.names = names
        self._lower = [_norm(n) for n in names]

    def query(self, q: str, limit: int = 15) -> list[str]:
        q = _norm(q)
        if not q:
            return []
        tokens = [t for t in _WORD_SPLIT.split(q) if t]

        scored: list[tuple[float, int, str]] = []  # (score, length, name)
        seen: set[int] = set()

        for i, low in enumerate(self._lower):
            name = self.names[i]
            if low.startswith(q):
                scored.append((100.0, len(name), name))
                seen.add(i)
            elif any(w.startswith(q) for w in _WORD_SPLIT.split(low)):
                scored.append((90.0, len(name), name))
                seen.add(i)
            elif tokens and all(t in low for t in tokens):
                scored.append((75.0, len(name), name))
                seen.add(i)

        # Fuzzy fallback only when exact tiers are thin - it's the slow path.
        if len(scored) < limit:
            candidates = {
                i: low for i, low in enumerate(self._lower) if i not in seen
            }
            for _low, score, i in process.extract(
                q,
                candidates,
                scorer=fuzz.partial_ratio,
                score_cutoff=72,
                limit=limit,
            ):
                scored.append((score * 0.7, len(self.names[i]), self.names[i]))

        scored.sort(key=lambda t: (-t[0], t[1], t[2]))
        return [name for _, _, name in scored[:limit]]


class VariantSearch:
    """SearchIndex plus metadata lookup for expanded item variants."""

    def __init__(self, variants: dict[str, Any]) -> None:
        self.variants = variants
        self.index = SearchIndex(list(variants.keys()))

    def query(self, q: str, limit: int = 15, item_type: str | None = None) -> list[Any]:
        # Over-fetch when filtering by type so post-filtering still fills the page.
        names = self.index.query(q, limit=limit * 4 if item_type else limit)
        out = []
        for name in names:
            v = self.variants[name]
            if item_type and v.item_type != item_type:
                continue
            out.append(v)
            if len(out) >= limit:
                break
        return out
