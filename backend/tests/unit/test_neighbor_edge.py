"""The line between two neighbouring places names the first factor that separates them."""
from types import SimpleNamespace

from app.services.matching import neighbor_edge


def _factor(key, label, contrib):
    return SimpleNamespace(key=key, label=label, contrib=contrib)


def test_the_earlier_factor_wins_over_a_larger_later_gap():
    higher = [_factor("role", "Роль", 0.20), _factor("test", "Тест", 0.50)]
    lower = [_factor("role", "Роль", 0.10), _factor("test", "Тест", 0.10)]
    edge = neighbor_edge(higher, lower)
    assert edge["key"] == "role"
    assert edge["points"] == 0.1
    assert "Роль" in edge["text"]


def test_a_missing_contribution_is_skipped():
    higher = [_factor("fsp", "ФСП", None), _factor("test", "Тест", 0.4)]
    lower = [_factor("fsp", "ФСП", None), _factor("test", "Тест", 0.2)]
    assert neighbor_edge(higher, lower)["key"] == "test"


def test_equal_factors_fall_through_to_a_shorter_queue():
    same = [_factor("test", "Тест", 0.4)]
    edge = neighbor_edge(same, same, higher_congestion=0.0, lower_congestion=0.05)
    assert edge["key"] == "queue"


def test_a_tie_has_no_line():
    same = [_factor("test", "Тест", 0.4)]
    assert neighbor_edge(same, same) is None
