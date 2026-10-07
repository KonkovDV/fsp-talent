"""An object that is not yours answers the same as an object that does not exist."""
import uuid
from types import SimpleNamespace

import pytest

from app.api.errors import ApiError
from app.api.v1.assessment import _own as own_session
from app.api.v1.messages import thread_side
from app.api.v1.needs import _own
from app.api.v1.tasks import _own_task


class _Db:
    def __init__(self, need):
        self.need = need

    async def get(self, _model, _need_id, with_for_update=False):
        return self.need


@pytest.mark.asyncio
async def test_another_employer_does_not_read_the_need():
    need = SimpleNamespace(employer_id=uuid.uuid4())
    with pytest.raises(ApiError) as caught:
        await _own(_Db(need), uuid.uuid4(), {"sub": str(uuid.uuid4())})
    assert caught.value.status_code == 404 and caught.value.code == "need_not_found"


@pytest.mark.asyncio
async def test_a_missing_need_is_the_same_answer():
    with pytest.raises(ApiError) as caught:
        await _own(_Db(None), uuid.uuid4(), {"sub": str(uuid.uuid4())})
    assert caught.value.status_code == 404


@pytest.mark.asyncio
async def test_the_owner_reads_the_need():
    owner = uuid.uuid4()
    need = SimpleNamespace(employer_id=owner)
    assert await _own(_Db(need), uuid.uuid4(), {"sub": str(owner)}) is need


@pytest.mark.asyncio
async def test_another_participant_does_not_read_the_session():
    owner = uuid.uuid4()
    session = SimpleNamespace(participant_id=owner, engine="cat_v2")
    with pytest.raises(ApiError) as caught:
        await own_session(_Db(session), uuid.uuid4(), {"sub": str(uuid.uuid4())})
    assert caught.value.status_code == 404
    assert await own_session(_Db(session), uuid.uuid4(), {"sub": str(owner)}) is session


@pytest.mark.asyncio
async def test_another_employer_does_not_read_the_task():
    owner = uuid.uuid4()
    task = SimpleNamespace(employer_id=owner)
    with pytest.raises(ApiError) as caught:
        await _own_task(_Db(task), uuid.uuid4(), uuid.uuid4())
    assert caught.value.status_code == 404
    assert await _own_task(_Db(task), uuid.uuid4(), owner) is task


def test_a_stranger_is_not_a_side_of_the_thread():
    offer = SimpleNamespace(candidate_id=uuid.uuid4(), employer_id=uuid.uuid4())
    assert thread_side(offer, "participant", uuid.uuid4()) is None
    assert thread_side(offer, "employer", offer.candidate_id) is None
    assert thread_side(offer, "participant", offer.candidate_id) == "participant"
    assert thread_side(offer, "employer", offer.employer_id) == "employer"
