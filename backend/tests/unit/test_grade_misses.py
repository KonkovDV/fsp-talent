from types import SimpleNamespace

from app.validation.grade_misses import split


def test_split_names_an_unconfirmed_overclaim_and_counts_confirmed_only():
    s = [SimpleNamespace(theta=-1.0, target="lead", earned=None),
         SimpleNamespace(theta=0.0, target="middle", earned="middle")]
    r = split(s)
    assert r["declared_above"] == 0.5 and r["ok"] == 0.5
    assert r["within_confirmed"] == 1.0
