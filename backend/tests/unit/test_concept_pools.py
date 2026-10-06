"""Two attempts must not share more than 40 % of the concept wordings."""
import random

from app.items.families.concept_pools import (
    LEVELS,
    SPECS,
    bank_ideas,
    draw_attempt,
    http_ideas,
    overlap,
    pick_bank,
)
from app.items.registry import CONCEPT_MAX_SHARE
from app.services.cat import MAX_ITEMS

HTTP_SPECS = frozenset({"backend", "frontend", "fullstack", "mobile", "devops", "security"})
SLOTS = int(CONCEPT_MAX_SHARE * MAX_ITEMS)


def test_each_specialization_has_six_ideas_and_several_wordings():
    assert SLOTS >= 1
    for spec in SPECS:
        ideas = bank_ideas(spec)
        assert len(ideas) >= 6, spec
        assert {idea.level for idea in ideas} == LEVELS[spec], spec
        assert len({idea.slug for idea in ideas}) == len(ideas)
        for idea in ideas:
            assert 3 <= len(idea.phrasings) <= 5, idea.id
            for phrasing in idea.phrasings:
                texts = [phrasing.right, *phrasing.wrong]
                assert len(texts) == len(set(texts))


def test_http_wordings_cover_every_level():
    by_level: dict[int, int] = {}
    for idea in http_ideas():
        by_level[idea.level] = by_level.get(idea.level, 0) + 1
        assert 3 <= len(idea.phrasings) <= 5
    assert set(by_level) == {1, 2, 3, 4, 5}


def test_two_attempts_share_at_most_forty_percent():
    rng = random.Random(7)
    for spec in SPECS:
        for level in sorted(LEVELS[spec]):
            first = draw_attempt(rng, spec, level, set(), SLOTS, http=spec in HTTP_SPECS)
            second = draw_attempt(rng, spec, level, set(first), SLOTS, http=spec in HTTP_SPECS)
            assert first, (spec, level)
            assert second, (spec, level)
            assert overlap(first, second) <= 0.40
            assert not (set(first) & set(second))


def test_one_attempt_does_not_repeat_an_idea():
    rng = random.Random(1)
    keys = draw_attempt(rng, "backend", 3, set(), SLOTS, http=True)
    ideas = [key.rsplit(":", 1)[0] for key in keys]
    assert len(ideas) == len(set(ideas))


def test_the_right_option_is_not_always_in_the_same_place():
    positions = {
        pick_bank(random.Random(seed), 3, "backend").correct
        for seed in range(30)
    }
    assert len(positions) > 1
