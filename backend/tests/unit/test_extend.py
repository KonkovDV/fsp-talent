"""The optional extra six items stay off until a validation run accepts them."""
from app.services import cat


def _band() -> cat.State:
    state = cat.State(spec="backend", target="middle")
    for i in range(20):
        state.responses.append(cat.Response(1.2, -0.2, 0.1, i >= 10))
    return state


def test_twenty_items_finish_when_extension_is_off():
    assert cat.ALLOW_EXTEND is False
    verdict = cat.evaluate(_band())
    assert verdict.done and verdict.stop_reason == "max_items"


def test_extension_is_offered_once_inside_the_band(monkeypatch):
    monkeypatch.setattr(cat, "ALLOW_EXTEND", True)
    state = _band()
    p = state.post().prob_at_least(cat.CUTS["middle"])
    assert cat.EXTEND_LOW <= p < cat.PASS_P
    offer = cat.evaluate(state)
    assert offer.stop_reason == "extend"
    state.extended = True
    again = cat.evaluate(state)
    assert again.stop_reason != "extend"
