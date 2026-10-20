"""A methodist answers a disputed result (152-FZ art. 16). Nobody sets a grade; a failed attempt can be voided."""
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.api.errors import ApiError
from app.api.v1 import assessment, methodist
from app.services import disputes
from app.services.disputes import (
    DEADLINE_DAYS,
    DisputeError,
    clean_note,
    clean_reason,
    clear_failed_checks,
    decide,
    voidable,
)
from app.services.session_marks import latest_failed_targets, latest_grade_flags

NOW = datetime(2026, 10, 20, 12, tzinfo=UTC)
NOTE = "Ключи заданий проверены, тест прошёл по правилам."


def _session(**extra):
    fields = dict(
        id=uuid.uuid4(), participant_id=uuid.uuid4(), engine="cat_v2", status="completed",
        flags={"outcome": "not_passed"}, specialization="backend", target_grade="middle", items_count=12,
        p_pass=0.41, theta_se=0.31, stop_reason="decided", started_at=NOW - timedelta(minutes=20),
        completed_at=NOW, grade_assigned=None,
    )
    fields.update(extra)
    return SimpleNamespace(**fields)


def _dispute(session, **extra):
    fields = dict(
        id=uuid.uuid4(), participant_id=session.participant_id, session_id=session.id, created_at=NOW,
        reason=None, status="open", decision_note=None, decided_at=None, decided_by=None,
    )
    fields.update(extra)
    return SimpleNamespace(**fields)


class Rows:
    def __init__(self, rows):
        self._rows = list(rows)

    def __iter__(self):
        return iter(self._rows)


class Desk:
    """A scripted session: get() answers in order, scalars() answers in order."""

    def __init__(self, gets=(), scalars=()):
        self.gets = list(gets)
        self.scalars_q = list(scalars)
        self.added = []
        self.commits = 0

    async def get(self, model, ident=None, **kwargs):
        return self.gets.pop(0) if self.gets else None

    async def scalars(self, stmt):
        return Rows(self.scalars_q.pop(0) if self.scalars_q else [])

    async def scalar(self, stmt):
        return None

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        self.commits += 1

    async def rollback(self):
        return None


def test_reason_is_optional_and_keeps_contacts_out():
    assert clean_reason(None) is None
    assert clean_reason("   ") is None
    assert clean_reason("  задание   про SQL  не открылось ") == "задание про SQL не открылось"
    with pytest.raises(DisputeError, match="identity"):
        clean_reason("пишите на anya@example.com")
    with pytest.raises(DisputeError, match="too_long"):
        clean_reason("а" * 1001)


def test_the_answer_has_a_length_and_no_contacts():
    assert clean_note(NOTE) == NOTE
    with pytest.raises(DisputeError, match="note_length"):
        clean_note("коротко")
    with pytest.raises(DisputeError, match="identity"):
        clean_note("Позвоните по номеру +7 999 123-45-67, разберёмся")


def test_only_a_failed_grade_test_can_be_voided():
    assert voidable(_session())
    assert not voidable(_session(flags={"outcome": "first_confirmation"}))
    assert not voidable(_session(flags={"outcome": "not_passed", "mode": "express"}))
    assert not voidable(_session(flags={"outcome": "not_passed", "vacancy_id": "v1"}))
    assert not voidable(_session(flags={"outcome": "not_passed", "voided": {"at": "x"}}))
    assert not voidable(_session(status="abandoned"))


def test_upholding_keeps_the_result_and_records_who_and_when():
    session = _session()
    dispute = _dispute(session)
    staff = uuid.uuid4()
    assert decide(dispute, session, "uphold", NOTE, staff, NOW) == "upheld"
    assert dispute.decision_note == NOTE and dispute.decided_at == NOW and dispute.decided_by == staff
    assert "voided" not in session.flags
    with pytest.raises(DisputeError, match="closed"):
        decide(dispute, session, "void", NOTE, staff, NOW)


def test_voiding_marks_the_attempt_and_never_touches_a_grade():
    session = _session(grade_assigned=None, flags={"outcome": "not_passed",
                                                   "lower_offer": {"grade": "middle", "p": 0.7}})
    dispute = _dispute(session)
    assert decide(dispute, session, "void", NOTE, uuid.uuid4(), NOW) == "voided"
    assert session.flags["voided"]["dispute"] == str(dispute.id)
    assert session.flags["outcome"] == "not_passed"
    assert "lower_offer" not in session.flags
    assert session.grade_assigned is None


def test_a_passed_attempt_cannot_be_voided_and_an_unknown_action_is_refused():
    session = _session(flags={"outcome": "upgrade"}, grade_assigned="senior")
    with pytest.raises(DisputeError, match="not_voidable"):
        decide(_dispute(session), session, "void", NOTE, uuid.uuid4(), NOW)
    with pytest.raises(DisputeError, match="action"):
        decide(_dispute(session), session, "raise_grade", NOTE, uuid.uuid4(), NOW)


def test_voiding_clears_only_the_failed_checks_of_that_attempt():
    failed = SimpleNamespace(tested_at=NOW, trust_level="self_reported", test_share=0.33, test_items=3)
    proven = SimpleNamespace(tested_at=NOW, trust_level="test_confirmed", test_share=0.9, test_items=4)
    older = SimpleNamespace(tested_at=NOW - timedelta(days=9), trust_level="self_reported", test_share=0.2,
                            test_items=5)
    assert clear_failed_checks([failed, proven, older], NOW) == 1
    assert failed.test_share is None and failed.test_items is None and failed.tested_at is None
    assert proven.test_share == 0.9 and older.test_items == 5
    assert clear_failed_checks([older], None) == 0


def test_a_voided_attempt_neither_lowers_matching_nor_marks_the_card():
    pid = uuid.uuid4()
    voided = {"outcome": "not_passed", "voided": {"at": "x"}, "tab_leaves": 5}
    older_pass = {"outcome": "first_confirmation"}
    rows = [(pid, "backend", "middle", voided), (pid, "backend", "junior", older_pass)]
    assert latest_failed_targets(rows) == {}
    assert latest_grade_flags([(pid, voided), (pid, older_pass)]) == {pid: older_pass}
    assert latest_failed_targets([(pid, "backend", "middle", {"outcome": "not_passed"})]) == {
        (pid, "backend"): "middle"}


def test_the_candidate_sees_the_status_and_the_legal_deadline():
    session = _session()
    view = disputes.candidate_view(_dispute(session, reason="задание не открылось"))
    assert view["status"] == "open" and view["status_label"] == "на рассмотрении"
    assert view["due_at"] == (NOW + timedelta(days=DEADLINE_DAYS)).isoformat()
    assert view["reason"] == "задание не открылось"


def test_the_desk_shows_the_attempt_without_the_person():
    session = _session(flags={"outcome": "not_passed", "tab_leaves": 3})
    row = disputes.desk_row(_dispute(session), session, NOW + timedelta(days=31))
    assert row["overdue"] is True
    attempt = row["attempt"]
    assert attempt["voidable"] is True and attempt["duration_s"] == 1200
    assert attempt["integrity_signals"] == ["tab_leaves"]
    assert not {"participant_id", "email", "display_name"} & set(attempt)


def test_item_rows_show_the_given_and_the_right_answer():
    item = SimpleNamespace(
        seq=1, family_id="py_eval", level=2, kind="code", topic="python", stem="Что выведет код?", code="print(6)",
        language="python", typed=True, options=["6"], correct_index=0, answer_index=None, answer_text="7",
        is_correct=False, timed_out=False, excluded=False, time_limit_s=180,
        served_at=NOW - timedelta(seconds=40), answered_at=NOW,
    )
    choice = SimpleNamespace(
        seq=2, family_id="concept", level=1, kind="concept", topic="concept", stem="Выберите", code=None,
        language=None, typed=False, options=["A", "B"], correct_index=1, answer_index=0, answer_text=None,
        is_correct=False, timed_out=True, excluded=False, time_limit_s=75, served_at=NOW, answered_at=None,
    )
    rows = disputes.item_rows([item, choice])
    assert rows[0]["given"] == "7" and rows[0]["right"] == "6" and rows[0]["spent_s"] == 40.0
    assert rows[1]["given"] == "A" and rows[1]["right"] == "B" and rows[1]["spent_s"] is None


class Bag(Desk):
    def __init__(self, gets=(), scalar=None):
        super().__init__(gets)
        self._scalar = scalar

    async def scalar(self, stmt):
        return self._scalar


async def test_a_dispute_stores_the_reason_and_returns_the_deadline():
    session = _session()
    current = {"sub": str(session.participant_id), "role": "participant"}
    db = Bag(gets=[session])
    out = await assessment.dispute_grade(session.id, current, db, assessment.DisputeIn(reason="задание не открылось"))
    assert out["status"] == "open" and "Грейд этой кнопкой не меняется" in out["text"]
    stored = db.added[0]
    assert stored.reason == "задание не открылось" and stored.status == "open"
    assert out["due_at"] == (stored.created_at + timedelta(days=DEADLINE_DAYS)).isoformat()


async def test_a_dispute_with_contacts_is_refused_before_anything_is_stored():
    session = _session()
    current = {"sub": str(session.participant_id), "role": "participant"}
    db = Bag(gets=[session])
    with pytest.raises(ApiError) as refused:
        await assessment.dispute_grade(session.id, current, db,
                                       assessment.DisputeIn(reason="звоните +7 999 123-45-67"))
    assert refused.value.status_code == 422 and db.added == []


async def test_the_candidate_lists_own_disputes():
    session = _session()
    current = {"sub": str(session.participant_id), "role": "participant"}
    db = Desk(scalars=[[_dispute(session)]])
    rows = await assessment.my_disputes(current, db)
    assert rows[0]["session_id"] == str(session.id) and rows[0]["status"] == "open"


def _staff(**extra):
    fields = dict(id=uuid.uuid4(), email="methodist@fsp.example", is_methodist=True, totp_secret=None,
                  totp_verified_at=None)
    fields.update(extra)
    return SimpleNamespace(**fields)


def _desk(monkeypatch, desk):
    @asynccontextmanager
    async def opened():
        yield desk

    monkeypatch.setattr(methodist, "_desk_session", opened)


async def test_the_desk_lists_open_disputes_for_staff_only(monkeypatch):
    staff = _staff()
    session = _session()
    _desk(monkeypatch, Desk(gets=[session], scalars=[[_dispute(session)]]))
    rows = await methodist.disputes("open", {"sub": str(staff.id), "role": "employer"}, Desk(gets=[staff]))
    assert rows[0]["attempt"]["target_grade"] == "middle" and rows[0]["status"] == "open"

    outsider = _staff(is_methodist=False)
    with pytest.raises(ApiError) as hidden:
        await methodist.disputes("open", {"sub": str(outsider.id), "role": "employer"}, Desk(gets=[outsider]))
    assert hidden.value.status_code == 404


async def test_voiding_through_the_desk_logs_and_tells_the_candidate(monkeypatch):
    staff = _staff()
    session = _session()
    dispute = _dispute(session)
    failed = SimpleNamespace(tested_at=session.completed_at, trust_level="self_reported", test_share=0.3,
                             test_items=3)
    rebuilt = []
    sent = []

    async def rebuild(db, person, *a, **k):
        rebuilt.append(person)

    async def notified(db, outbox, role, recipient, kind, title, body, link):
        sent.append((role, recipient, kind, body))

    monkeypatch.setattr("app.services.profile.rebuild_profile", rebuild)
    monkeypatch.setattr(methodist, "notify", notified)
    person = SimpleNamespace(id=session.participant_id)
    desk = Desk(gets=[dispute, session, person], scalars=[[failed]])
    _desk(monkeypatch, desk)
    body = methodist.DecisionIn(action="void", note=NOTE)
    out = await methodist.decide_dispute(dispute.id, body, {"sub": str(staff.id), "role": "employer"},
                                         Desk(gets=[staff]))
    assert out["status"] == "voided" and out["attempt"]["voided"] is True
    assert failed.test_items is None and rebuilt == [person] and desk.commits == 1
    log = [obj for obj in desk.added if getattr(obj, "action", "") == "dispute_voided"]
    assert log and log[0].employer_id == staff.id
    assert sent and sent[0][:3] == ("participant", session.participant_id, "dispute_decided")


async def test_the_desk_refuses_a_second_decision(monkeypatch):
    staff = _staff()
    session = _session()
    dispute = _dispute(session, status="upheld")
    _desk(monkeypatch, Desk(gets=[dispute, session]))
    with pytest.raises(ApiError) as twice:
        await methodist.decide_dispute(dispute.id, methodist.DecisionIn(action="uphold", note=NOTE),
                                       {"sub": str(staff.id), "role": "employer"}, Desk(gets=[staff]))
    assert twice.value.status_code == 409
