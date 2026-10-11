"""audit-3 P1-1: aggregates use the search's visibility rule, and small rankings are not published."""
import inspect

from app.api.v1 import offers, public
from app.services.search import pipeline


def test_market_and_ranking_use_the_shared_rule():
    assert "visible_in_search()" in inspect.getsource(offers.offer_market)
    ranking = inspect.getsource(public.category_ranking)
    assert "visible_in_search()" in ranking and "len(values) < BANK_MIN" in ranking


def test_the_rule_covers_deletion_age_and_job_search():
    rule = inspect.getsource(pipeline._in_search)
    for clause in ("deleted_at.is_(None)", "suspended_at.is_(None)", 'job_search != "not_looking"',
                   "birth_date.is_not(None)", "minor_consent_given"):
        assert clause in rule, clause
    assert pipeline.BANK_MIN == 5
