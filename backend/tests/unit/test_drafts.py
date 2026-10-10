import pytest

from app.items.registry import FAMILIES
from app.services.ai import drafts, providers


def test_two_keys_must_agree_and_the_stem_must_not_carry_a_person():
    assert drafts.judge("Сколько будет 2 + 2?", "4", "4").accepted
    assert drafts.judge("Сколько будет 2 + 2?", "4", "5").reason == "disagree"
    leaked = drafts.judge("Ответ равен 4", "4", "4")
    assert leaked.reason == "leaked_in_stem" and not leaked.accepted
    named = drafts.judge("Напишите Анне Ивановой", "4", "4")
    assert named.reason == "identity"
    mailed = drafts.judge("Письмо на a@demo.talent", "4", "4")
    assert mailed.reason == "identity"
    assert drafts.judge("Сколько будет 2 + 2?", "4", "4").served is False


def test_a_review_happens_once_and_keeps_people_out_of_the_note():
    from datetime import UTC, datetime

    from app.models import ItemDraft

    row = ItemDraft(spec="backend", topic="python", level=2, stem="Сколько?", key="6", status="pending")
    now = datetime(2026, 10, 10, tzinfo=UTC)
    with pytest.raises(ValueError, match="identity"):
        drafts.review(row, "approved", "Передать Анне Ивановой", now)
    assert drafts.review(row, "rejected", None, now).status == "rejected" and row.reviewed_at == now
    with pytest.raises(ValueError, match="already_reviewed"):
        drafts.review(row, "approved", None, now)
    assert drafts.brief_error("backend", "python", 3) is None
    assert drafts.brief_error("backend", "python", 9) and drafts.brief_error("nope", "python", 1)


def test_a_served_draft_cannot_be_constructed():
    with pytest.raises(RuntimeError):
        drafts.Verdict(True, "agree", served=True)


async def test_the_checker_does_not_see_the_key_and_the_bank_stays(monkeypatch):
    calls = []

    async def fake(model, system, user):
        calls.append((model, system, user))
        if model == "writer":
            return '{"stem": "Сколько раз выполнится цикл?", "key": "6"}'
        return '{"key": "6"}'

    monkeypatch.setattr(drafts, "_chat", fake)
    monkeypatch.setattr(providers.settings, "AI_ENABLED", True)
    monkeypatch.setattr(providers.settings, "GIGACHAT_CREDENTIALS", "present")
    monkeypatch.setattr(providers.settings, "GIGACHAT_MODEL", "writer")
    monkeypatch.setattr(providers.settings, "GIGACHAT_CHECK_MODEL", "checker")
    before = set(FAMILIES)
    verdict = await drafts.propose("backend", "python", 1)
    assert verdict.accepted and verdict.reason == "agree" and verdict.served is False
    assert calls[0][2] == "Специализация: backend. Тема: python. Уровень: 1."
    assert calls[1][0] == "checker"
    assert calls[1][2] == "Сколько раз выполнится цикл?"
    assert "6" not in calls[1][2]
    assert set(FAMILIES) == before


async def test_drafts_stay_off_without_a_second_model(monkeypatch):
    async def fail(*_args):
        raise AssertionError("the model must not be called")

    monkeypatch.setattr(drafts, "_chat", fail)
    monkeypatch.setattr(providers.settings, "AI_ENABLED", True)
    monkeypatch.setattr(providers.settings, "GIGACHAT_CREDENTIALS", "present")
    monkeypatch.setattr(providers.settings, "GIGACHAT_MODEL", "writer")
    monkeypatch.setattr(providers.settings, "GIGACHAT_CHECK_MODEL", "")
    off = await drafts.propose("backend", "python", 1)
    assert off.reason == "model_off" and not off.accepted
    monkeypatch.setattr(providers.settings, "GIGACHAT_CHECK_MODEL", "writer")
    same = await drafts.propose("backend", "python", 1)
    assert same.reason == "same_model"
