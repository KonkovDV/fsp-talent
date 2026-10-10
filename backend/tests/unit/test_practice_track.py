import pytest

from app.services.practice_track import next_stage


def test_practice_moves_one_step_and_can_close():
    assert next_stage("sent", "screening") == "screening"
    assert next_stage("trial", "hired") == "hired"
    assert next_stage("screening", "closed") == "closed"


def test_practice_does_not_skip_or_reopen():
    with pytest.raises(ValueError):
        next_stage("sent", "hired")
    with pytest.raises(ValueError):
        next_stage("closed", "sent")
    with pytest.raises(ValueError):
        next_stage("hired", "trial")
