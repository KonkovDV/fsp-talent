import pytest

from app.items.registry import FAMILIES
from app.services.ai import drafts


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
    monkeypatch.setattr(drafts.settings, "AI_ENABLED", True)
    monkeypatch.setattr(drafts.settings, "GIGACHAT_CREDENTIALS", "present")
    monkeypatch.setattr(drafts.settings, "GIGACHAT_MODEL", "writer")
    monkeypatch.setattr(drafts.settings, "GIGACHAT_CHECK_MODEL", "checker")
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
    monkeypatch.setattr(drafts.settings, "AI_ENABLED", True)
    monkeypatch.setattr(drafts.settings, "GIGACHAT_CREDENTIALS", "present")
    monkeypatch.setattr(drafts.settings, "GIGACHAT_MODEL", "writer")
    monkeypatch.setattr(drafts.settings, "GIGACHAT_CHECK_MODEL", "")
    off = await drafts.propose("backend", "python", 1)
    assert off.reason == "model_off" and not off.accepted
    monkeypatch.setattr(drafts.settings, "GIGACHAT_CHECK_MODEL", "writer")
    same = await drafts.propose("backend", "python", 1)
    assert same.reason == "same_model"
