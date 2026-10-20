"""A person answers a disputed test result (152-FZ art. 16, parts 3-4: an objection to an automated decision).

The reviewer is a methodist. Nobody sets a grade by hand: the only remedy is to void an attempt that did not
confirm a grade. A voided attempt no longer locks a retake, no longer lowers the grade that matching reads,
its integrity marks leave the card, and the "checked by the test, not confirmed" marks it left on skills are
cleared. Skills the attempt confirmed stay confirmed: voiding removes the consequences of a failure, not the
right answers. The reviewer sees the attempt, not the person: no name, e-mail or contacts.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from app.services.ai.assistant import has_identity
from app.services.session_marks import integrity_level, is_voided

DEADLINE_DAYS = 30
REASON_MAX = 1000
NOTE_MIN = 10
NOTE_MAX = 1000
ACTIONS = ("uphold", "void")
STATUS_RU = {"open": "на рассмотрении", "upheld": "результат оставлен", "voided": "попытка аннулирована"}


class DisputeError(ValueError):
    """The dispute or the decision cannot be stored; the message is a short machine reason."""


def due_at(created_at: datetime) -> datetime:
    return created_at + timedelta(days=DEADLINE_DAYS)


def _one_line(text: str | None) -> str:
    return " ".join((text or "").split())


def clean_reason(text: str | None) -> str | None:
    """The candidate's own words. Contacts and names stay out: the methodist reviews the attempt, not the person."""
    reason = _one_line(text)
    if not reason:
        return None
    if len(reason) > REASON_MAX:
        raise DisputeError("too_long")
    if has_identity(reason):
        raise DisputeError("identity")
    return reason


def clean_note(text: str | None) -> str:
    note = _one_line(text)
    if not NOTE_MIN <= len(note) <= NOTE_MAX:
        raise DisputeError("note_length")
    if has_identity(note):
        raise DisputeError("identity")
    return note


def voidable(session) -> bool:
    """A finished grade test that did not confirm its grade. A trial and a vacancy test never count."""
    flags = getattr(session, "flags", None) or {}
    return (
        getattr(session, "status", None) == "completed"
        and flags.get("outcome") == "not_passed"
        and flags.get("mode") != "express"
        and not flags.get("vacancy_id")
        and not is_voided(flags)
    )


def decide(dispute, session, action: str, note: str | None, staff_id, now: datetime) -> str:
    """Close an open dispute. Returns the new status. The caller writes the log and tells the candidate."""
    if getattr(dispute, "status", "open") != "open":
        raise DisputeError("closed")
    if action not in ACTIONS:
        raise DisputeError("action")
    text = clean_note(note)
    if action == "void":
        if not voidable(session):
            raise DisputeError("not_voidable")
        flags = dict(session.flags or {})
        flags["voided"] = {"at": now.isoformat(), "dispute": str(dispute.id)}
        # A voided attempt must not leave a lower-grade offer that can still be accepted.
        flags.pop("lower_offer", None)
        session.flags = flags
        dispute.status = "voided"
    else:
        dispute.status = "upheld"
    dispute.decision_note = text
    dispute.decided_at = now
    dispute.decided_by = staff_id
    return dispute.status


def clear_failed_checks(skills, completed_at: datetime | None) -> int:
    """Drop the "checked, not confirmed" marks that the voided attempt left. Confirmed skills keep their proof."""
    if completed_at is None:
        return 0
    cleared = 0
    for row in skills:
        if getattr(row, "tested_at", None) == completed_at and getattr(row, "trust_level", None) != "test_confirmed":
            row.test_share = None
            row.test_items = None
            row.tested_at = None
            cleared += 1
    return cleared


def candidate_view(dispute) -> dict:
    """What the candidate reads about their own dispute."""
    return {
        "id": str(dispute.id),
        "session_id": str(dispute.session_id),
        "status": dispute.status,
        "status_label": STATUS_RU.get(dispute.status, dispute.status),
        "reason": dispute.reason,
        "decision_note": dispute.decision_note,
        "created_at": dispute.created_at.isoformat(),
        "due_at": due_at(dispute.created_at).isoformat(),
        "decided_at": dispute.decided_at.isoformat() if dispute.decided_at else None,
    }


def attempt_facts(session) -> dict:
    """The attempt as the methodist sees it: what was tested and how it ended, without the person."""
    flags = session.flags or {}
    duration = None
    if session.completed_at and session.started_at:
        duration = int((session.completed_at - session.started_at).total_seconds())
    level = integrity_level(flags)
    return {
        "session_id": str(session.id),
        "specialization": session.specialization,
        "target_grade": session.target_grade,
        "status": session.status,
        "outcome": flags.get("outcome"),
        "items_count": session.items_count,
        "p_pass": session.p_pass,
        "theta_se": session.theta_se,
        "stop_reason": session.stop_reason,
        "started_at": session.started_at.isoformat() if session.started_at else None,
        "completed_at": session.completed_at.isoformat() if session.completed_at else None,
        "duration_s": duration,
        "integrity_level": level["level"],
        "integrity_signals": list(level["signals"]),
        "person_fit_review": bool((flags.get("person_fit") or {}).get("review")),
        "voidable": voidable(session),
        "voided": is_voided(flags),
    }


def item_rows(items) -> list[dict]:
    """Served items with the given and the right answer, so a broken key or a timing fault is visible."""
    out = []
    for it in items:
        if it.typed:
            right = it.options[it.correct_index] if it.options else None
            given = it.answer_text
        else:
            right = it.options[it.correct_index] if it.options and 0 <= it.correct_index < len(it.options) else None
            given = it.options[it.answer_index] if it.answer_index is not None and it.options \
                and 0 <= it.answer_index < len(it.options) else None
        spent = None
        if it.answered_at and it.served_at:
            spent = round((it.answered_at - it.served_at).total_seconds(), 1)
        out.append({
            "seq": it.seq, "family_id": it.family_id, "level": it.level, "kind": it.kind, "topic": it.topic,
            "stem": it.stem, "code": it.code, "language": it.language, "given": given, "right": right,
            "correct": it.is_correct, "timed_out": it.timed_out, "excluded": it.excluded,
            "time_limit_s": it.time_limit_s, "spent_s": spent,
        })
    return out


def desk_row(dispute, session, now: datetime) -> dict:
    due = due_at(dispute.created_at)
    return {
        **candidate_view(dispute),
        "overdue": dispute.status == "open" and now > due,
        "attempt": attempt_facts(session) if session is not None else None,
    }
