"""JS-02: expert mode runs the live CAT on a simulated candidate and gives away no item content."""
import json
import random
import time

import pytest
from starlette.requests import Request

from app.api.errors import ApiError
from app.api.v1 import public
from app.items import LEVEL_B
from app.services import cat
from app.services.cat import CUTS, MAX_ITEMS, Response, State
from app.validation import assessment, expert_mode
from app.validation.expert_mode import simulate

STEP_KEYS = {"n", "family", "topic", "level", "difficulty", "correct", "theta", "se", "p_pass"}


def _request() -> Request:
    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}
    return Request({"type": "http", "method": "GET", "path": "/", "headers": [], "client": ("10.0.0.1", 9)}, receive)


def test_same_seed_gives_the_same_session_and_a_new_seed_fresh_items():
    first = simulate(grade="middle", seed=11)
    assert simulate(grade="middle", seed=11) == first
    other = simulate(grade="middle", seed=12)
    assert [s["family"] for s in other["steps"]] != [s["family"] for s in first["steps"]] or \
        [s["correct"] for s in other["steps"]] != [s["correct"] for s in first["steps"]]


def test_steps_follow_the_production_posterior_and_decision():
    out = simulate(grade="senior", seed=5)
    steps = out["steps"]
    assert out["theta"] == CUTS["senior"] + 0.5 and out["target"] == "senior" and out["true_grade"] == "senior"
    assert len(steps) == out["items"] and cat.MIN_ITEMS <= out["items"] <= MAX_ITEMS
    assert [s["n"] for s in steps] == list(range(1, len(steps) + 1))
    # The last step is the estimate the session ended on.
    assert steps[-1]["theta"] == out["theta_hat"] and steps[-1]["se"] == out["se"]
    # No calibration offsets: the served difficulty is the level's prior b from the bank.
    assert all(s["difficulty"] == round(LEVEL_B[s["level"]], 2) for s in steps)
    # The verdict is cat.decide on the same answers.
    rebuilt = State(spec="backend", target="senior")
    session = assessment.run_session(out["theta"], "backend", "senior", expert_mode._bank_truth(), random.Random(5))
    rebuilt.responses = [Response(a, b, c, ok, fam) for _k, fam, a, b, c, ok in session.answers]
    decided = cat.decide(rebuilt)
    assert (decided.earned, decided.passed) == (out["earned"], out["passed"])
    assert out["stop_reason"]


def test_no_item_text_options_or_keys_leave_the_module():
    out = simulate(grade="junior", spec="frontend", seed=3, batch=5)
    assert all(set(step) == STEP_KEYS for step in out["steps"])
    blob = json.dumps(out, ensure_ascii=False)
    for word in ("stem", "options", "answer", "correct_index", "code", "static_key"):
        assert f'"{word}"' not in blob


def test_batch_of_fifty_reports_agreement_quickly():
    started = time.perf_counter()
    out = simulate(grade="middle", seed=7, batch=50)
    assert time.perf_counter() - started < 2.0
    batch = out["batch"]
    assert batch["n"] == 50 and sum(batch["grades"].values()) == 50
    assert 0.0 <= batch["same_as_first"] <= 1.0 and 0.0 <= batch["same_as_truth"] <= 1.0
    # Far above the cut the same test confirms the target almost every time.
    far = simulate(theta=CUTS["middle"] + 1.4, target="middle", seed=7, batch=50)["batch"]
    assert far["passed"] >= 0.9


def test_bad_input_is_refused():
    for kwargs in ({"spec": "cobol"}, {"grade": "guru"}, {"theta": 9.0}, {"batch": 51},
                   {"grade": "middle", "target": "boss"}):
        with pytest.raises(ValueError):
            simulate(**kwargs)


def test_truth_seed_is_apart_from_validation_seeds():
    assert expert_mode.EXPERT_TRUTH_SEED not in {7, 2026, 2027, 2028, *range(101, 106), *range(201, 206),
                                                 *range(3001, 3006), *range(4001, 4006)}


async def test_endpoint_is_rate_limited_and_validates(monkeypatch):
    async def limited(*_a, **_k):
        return True

    async def allow(*_a, **_k):
        return False

    monkeypatch.setattr(public, "too_many", limited)
    with pytest.raises(ApiError) as err:
        await public.simulate_assessment(_request(), spec="backend", grade="middle", theta=None, target=None,
                                         seed=1, batch=0)
    assert err.value.status_code == 429
    monkeypatch.setattr(public, "too_many", allow)
    body = await public.simulate_assessment(_request(), spec="backend", grade="middle", theta=None,
                                            target=None, seed=1, batch=3)
    assert body["batch"]["n"] == 3 and body["steps"]
    with pytest.raises(ApiError) as err:
        await public.simulate_assessment(_request(), spec="nope", grade="middle", theta=None, target=None,
                                         seed=1, batch=0)
    assert err.value.status_code == 422
