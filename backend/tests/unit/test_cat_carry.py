from types import SimpleNamespace

from app.services.assessment import carried_responses, seed_carried
from app.services.cat import State


def _item(**kw):
    base = dict(a=1.0, b=0.0, c=0.1, is_correct=True, family_id="py", item_key="py:1", excluded=False)
    base.update(kw)
    return SimpleNamespace(**base)


def test_unscored_and_excluded_answers_are_not_carried():
    items = [_item(), _item(is_correct=None, item_key="blank"), _item(excluded=True, item_key="drop")]
    assert len(carried_responses(items)) == 1
    state = State(spec="backend", target="middle")
    assert seed_carried(state, items) == 1
    assert state.keys_used == {"py:1"}
    assert state.families_used["py"] == 1
