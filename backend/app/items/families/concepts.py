"""Concept items: a finite pool of ideas, several wordings each, capped at 30 % of a session.

The right answer is not a computed number, so the pool can be memorised. A wording that this candidate
has already seen is not served again. One idea is not asked twice in the same attempt.
"""
from __future__ import annotations

import random

from app.items import Family, Item
from app.items.families.concept_pools import has_bank, pick_bank, pick_http

ALL_SPECS = frozenset({"backend", "frontend", "fullstack", "ml", "devops", "security", "embedded", "mobile"})


def bank_generate(rng: random.Random, level: int, spec: str, avoid: set[str] | None = None,
                  used_ideas: set[str] | None = None) -> Item:
    item = pick_bank(rng, level, spec, avoid, used_ideas)
    if item is None:
        raise LookupError(f"no fresh concept item for {spec} level {level}")
    return item


def http_generate(rng: random.Random, level: int, spec: str, avoid: set[str] | None = None,
                  used_ideas: set[str] | None = None) -> Item:
    del spec
    item = pick_http(rng, level, avoid, used_ideas)
    if item is None:
        raise LookupError(f"no fresh HTTP item at level {level}")
    return item


BANK = Family(
    id="concept_bank", title="Понимание: вопросы по специализации", topic="concept", kind="concept",
    specs=ALL_SPECS, skills=(), generate=bank_generate, a=1.0, supports=has_bank, languages=(),
)
HTTP_FAMILY = Family(
    id="concept_http", title="Понимание: семантика HTTP", topic="concept", kind="concept",
    specs=frozenset({"backend", "frontend", "fullstack", "mobile", "devops", "security"}), skills=(),
    generate=http_generate, a=1.0, languages=(),
)
