"""Extra resumes: a declared grade in another specialization, below a passed test, at most two of them."""
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest

from app.api.errors import ApiError
from app.api.v1 import resumes as api
from app.services import resumes
from app.services.search.pipeline import _role_for_need, shown_category

NOW = datetime(2026, 10, 10, 9, 0, tzinfo=UTC)


def test_a_resume_is_checked_before_it_is_kept():
    draft = resumes.clean("mobile", "junior", ["kotlin", "Kotlin", " swift "], "  Пишу под Android  ", "backend")
    assert draft.specialization == "mobile" and draft.grade == "junior"
    assert len(draft.stack) == len({s.lower() for s in draft.stack}) == 2
    assert draft.summary == "Пишу под Android"
    for spec, grade, summary, primary, text in [
        ("cooking", "junior", None, "backend", "Специализацию"),
        ("backend", "junior", None, "backend", "уже указана"),
        ("mobile", "guru", None, "backend", "Грейд"),
        ("mobile", "junior", "x" * (resumes.SUMMARY_MAX + 1), "backend", "длиннее"),
        ("mobile", "junior", "Пишите на ivan@mail.ru", "backend", "контактов"),
    ]:
        with pytest.raises(ValueError, match=text):
            resumes.clean(spec, grade, [], summary, primary)
    with pytest.raises(ValueError, match="Не больше"):
        resumes.clean("mobile", "junior", [f"tech{i}" for i in range(resumes.STACK_MAX + 1)], None, "backend")


def test_a_passed_test_outranks_the_resume_and_the_primary_stays_beside_it():
    cat = SimpleNamespace(primary_role="backend", grade="middle", grade_source="assessed")
    resume = SimpleNamespace(specialization="mobile", grade="junior")
    assert _role_for_need(cat, "mobile", None, resume) == ("mobile", "junior", "declared")
    confirmed = SimpleNamespace(specialization="mobile", grade="middle")
    assert _role_for_need(cat, "mobile", confirmed, resume) == ("mobile", "middle", "assessed")
    assert _role_for_need(cat, "backend", None, resume) == ("backend", "middle", "assessed")
    assert _role_for_need(cat, None, None, resume) == ("backend", "middle", "assessed")
    role, grade, source, also = shown_category("backend", "middle", "assessed", "mobile", "junior", "declared")
    assert (role, grade, source) == ("mobile", "junior", "declared") and also["role"] == "backend"


class Scalars:
    def __init__(self, items):
        self.items = items

    def __iter__(self):
        return iter(self.items)


class Db:
    def __init__(self, person, rows=()):
        self.person, self.rows, self.added, self.deleted, self.commits = person, list(rows), [], [], 0

    async def get(self, model, ident, **kwargs):
        if model is api.Participant:
            return self.person
        return next((r for r in self.rows if r.id == ident), None)

    async def scalars(self, stmt):
        return Scalars(list(self.rows))

    def add(self, obj):
        obj.id = obj.id or uuid.uuid4()
        obj.created_at = obj.updated_at = NOW
        self.rows.append(obj)
        self.added.append(obj)

    async def delete(self, obj):
        self.rows.remove(obj)
        self.deleted.append(obj)

    async def flush(self):
        return None

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        return None


@pytest.fixture
def quiet(monkeypatch):
    async def nothing(*_args, **_kwargs):
        return None

    monkeypatch.setattr(api, "rebuild_profile", nothing)
    monkeypatch.setattr(api, "bump_bank_epoch", nothing)


async def test_three_resumes_at_most_and_only_ones_own(quiet):
    me = SimpleNamespace(id=uuid.uuid4(), specialization="backend", declared_grade="middle", assessed_grade=None)
    current = {"sub": str(me.id), "role": "participant"}
    db = Db(me)
    listed = await api.add_resume(api.ResumeIn(specialization="mobile", grade="junior", stack=["kotlin"]), current, db)
    assert listed["primary"]["specialization"] == "backend" and listed["primary"]["grade_source"] == "declared"
    assert [r["specialization"] for r in listed["extras"]] == ["mobile"] and db.commits == 1

    with pytest.raises(ApiError) as twice:
        await api.add_resume(api.ResumeIn(specialization="mobile", grade="middle"), current, db)
    assert twice.value.status_code == 409
    await api.add_resume(api.ResumeIn(specialization="qa", grade="junior"), current, db)
    with pytest.raises(ApiError) as fourth:
        await api.add_resume(api.ResumeIn(specialization="data", grade="junior"), current, db)
    assert fourth.value.status_code == 409 and "3" in fourth.value.detail
    with pytest.raises(ApiError) as bad:
        await api.add_resume(api.ResumeIn(specialization="backend", grade="junior"), current, db)
    assert bad.value.status_code == 422

    mobile = db.rows[0]
    changed = await api.update_resume(mobile.id, api.ResumeIn(specialization="mobile", grade="middle",
                                                              summary="Два приложения в сторе"), current, db)
    assert changed["extras"][0]["grade"] == "middle" and changed["extras"][0]["summary"] == "Два приложения в сторе"

    stranger = {"sub": str(uuid.uuid4()), "role": "participant"}
    foreign = Db(SimpleNamespace(id=uuid.UUID(stranger["sub"]), specialization="qa", assessed_grade=None), db.rows)
    with pytest.raises(ApiError) as hidden:
        await api.delete_resume(mobile.id, stranger, foreign)
    assert hidden.value.status_code == 404 and not foreign.deleted

    left = await api.delete_resume(mobile.id, current, db)
    assert [r["specialization"] for r in left["extras"]] == ["qa"]


async def test_the_survey_comes_first(quiet):
    me = SimpleNamespace(id=uuid.uuid4(), specialization=None, declared_grade=None, assessed_grade=None)
    with pytest.raises(ApiError) as early:
        await api.add_resume(api.ResumeIn(specialization="mobile", grade="junior"),
                             {"sub": str(me.id), "role": "participant"}, Db(me))
    assert early.value.status_code == 409
