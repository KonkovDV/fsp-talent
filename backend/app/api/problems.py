"""RFC 9457 classes for the API.

The specific machine code stays in `code`. `problem` is one of E01–E20, a stable class a client
can branch on without listing every code. `type` is a path on this API.
"""
from __future__ import annotations

CLASSES: dict[str, str] = {
    "E01": "Вход",
    "E02": "Доступ",
    "E03": "Не найдено",
    "E04": "Конфликт",
    "E05": "Поля запроса",
    "E06": "Слишком часто",
    "E07": "Подтверждение почты",
    "E08": "Согласие",
    "E09": "Тест",
    "E10": "Приглашение",
    "E11": "Задание",
    "E12": "Метод",
    "E13": "Уже нет",
    "E14": "Слишком большой запрос",
    "E15": "Сбой сервера",
    "E16": "Сервис недоступен",
    "E17": "Грейд",
    "E18": "Сессия теста",
    "E19": "Вилка",
    "E20": "Демо-аккаунт",
}

CODE_CLASS: dict[str, str] = {
    "unauthorized": "E01",
    "invalid_credentials": "E01",
    "email_not_verified": "E01",
    "totp_required": "E01",
    "totp_invalid": "E01",
    "refresh_superseded": "E01",
    "fsp_ticket_invalid": "E01",
    "fsp_invalid": "E01",
    "forbidden": "E02",
    "account_suspended": "E02",
    "csrf_invalid": "E02",
    "contacts_hidden": "E02",
    "demo_reset_forbidden": "E02",
    "contacts_revoked": "E02",
    "consent_withdrawn": "E02",
    "not_found": "E03",
    "need_not_found": "E03",
    "fsp_not_found": "E03",
    "consent_unknown": "E03",
    "conflict": "E04",
    "email_taken": "E04",
    "fsp_taken": "E04",
    "fsp_already_linked": "E04",
    "birth_date_locked": "E04",
    "complaint_duplicate": "E04",
    "validation_error": "E05",
    "bad_request": "E05",
    "delete_confirm": "E05",
    "survey_required": "E05",
    "too_young": "E05",
    "reserved_email": "E05",
    "nul_byte": "E05",
    "age_mismatch": "E05",
    "rate_limited": "E06",
    "resend_cooldown": "E06",
    "verification_attempts": "E06",
    "retake_cooldown": "E06",
    "decline_pause": "E06",
    "verification_invalid": "E07",
    "verification_expired": "E07",
    "consent_required": "E08",
    "task_closed": "E11",
    "task_answered": "E11",
    "sandbox_unavailable": "E11",
    "method_not_allowed": "E12",
    "gone": "E13",
    "payload_too_large": "E14",
    "internal_error": "E15",
    "unavailable": "E16",
    "grade_locked": "E17",
    "lower_offer_closed": "E17",
    "session_closed": "E18",
    "session_expired": "E18",
    "item_token_invalid": "E18",
    "question_bank_empty": "E09",
    "offer_closed": "E10",
    "offer_expired": "E10",
    "invites_paused": "E10",
    "salary_required": "E19",
    "demo_protected": "E20",
}


def problem_class(code: str) -> str:
    return CODE_CLASS[code]


def problem_fields(code: str, status: int, instance: str | None) -> dict:
    klass = CODE_CLASS[code]
    return {
        "type": f"/problems/{klass}",
        "title": CLASSES[klass],
        "status": status,
        "instance": instance,
        "problem": klass,
    }


def catalog() -> list[dict]:
    by_class: dict[str, list[str]] = {key: [] for key in CLASSES}
    for code, klass in CODE_CLASS.items():
        by_class[klass].append(code)
    return [
        {"problem": key, "title": title, "type": f"/problems/{key}", "codes": sorted(by_class[key])}
        for key, title in CLASSES.items()
    ]
