"""Each confirmed skill on the card names its source, date and method; self-reported skills get no entry."""
import inspect

from app.services.search import pipeline


def test_only_confirmed_trust_levels_have_a_method():
    assert set(pipeline.SKILL_METHODS) == {"test_confirmed", "resume_confirmed"}
    assert all(pipeline.SKILL_METHODS.values())


def test_card_carries_provenance_next_to_the_old_fields():
    source = inspect.getsource(pipeline._build_cards)
    assert '"skill_provenance": provenance.get(pid, {})' in source
    assert "Skill.trust_level.in_(tuple(SKILL_METHODS))" in source
