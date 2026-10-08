"""The family knife ignores a pass that disappears when one family is left out."""
from app.services import cat


def _state() -> cat.State:
    state = cat.State(spec="backend", target="middle")
    for _ in range(16):
        state.responses.append(cat.Response(2.0, -1.8, 0.0, True, "solver"))
    for _ in range(2):
        state.responses.append(cat.Response(1.0, 1.5, 0.0, False, "other"))
    return state


def test_knife_is_off_by_default():
    assert cat.FAMILY_KNIFE is False
    assert cat.MAX_PER_FAMILY == 5
    assert cat.family_knife_holds(_state()) is True


def test_knife_rejects_a_pass_that_one_family_carries(monkeypatch):
    monkeypatch.setattr(cat, "FAMILY_KNIFE", True)
    state = _state()
    held = cat.family_knife_holds(state)
    full = state.post().prob_at_least(cat.CUTS["middle"])
    others = [row for row in state.responses if row.family_id != "solver"]
    left_out = cat.posterior(others, prior_mean=cat.CUTS["middle"]).prob_at_least(cat.CUTS["middle"])
    assert full >= cat.PASS_P
    assert left_out < cat.KNIFE_FLOOR
    assert held is False
    assert cat.decide(state).passed is False
