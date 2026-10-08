"""One error format for the whole API.

Every error body is

    {"error": {"code": "<machine code>", "message": "<text for a person>", "details": ...},
     "detail": <the same message, or the list of validation errors>}

`detail` stays for clients written against FastAPI defaults; new clients read `error.code`.
The full list of codes is in docs/API_ERRORS.md and is checked by a unit test.
"""
from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)

# Default code per HTTP status when the raising code did not name one.
STATUS_CODES: dict[int, str] = {
    400: "bad_request",
    401: "unauthorized",
    403: "forbidden",
    404: "not_found",
    405: "method_not_allowed",
    409: "conflict",
    410: "gone",
    422: "validation_error",
    429: "rate_limited",
    500: "internal_error",
    503: "unavailable",
}

# Codes raised explicitly with ApiError. Keep in sync with docs/API_ERRORS.md (a test checks it).
ERROR_CODES: dict[str, str] = {
    **{code: f"HTTP {http}" for http, code in STATUS_CODES.items()},
    "invalid_credentials": "Неверный email или пароль",
    "email_not_verified": "Email не подтверждён: введите код из письма",
    "email_taken": "Аккаунт с таким email уже есть",
    "verification_invalid": "Код или ссылка не подходят",
    "verification_expired": "Срок кода истёк, запросите новый",
    "verification_attempts": "Слишком много неверных попыток, запросите новый код",
    "resend_cooldown": "Новый код можно запросить через минуту",
    "consent_required": "Нужно согласие на обработку данных",
    "consent_unknown": "Нет такого документа",
    "consent_withdrawn": "Кандидат отозвал согласие на обработку данных: контакты недоступны",
    "delete_confirm": "Чтобы удалить аккаунт, введите слово «удалить»",
    "fsp_invalid": "Неверные учётные данные ФСП",
    "fsp_taken": "Этот ФСП ID уже привязан к другому аккаунту",
    "fsp_already_linked": "К аккаунту уже привязан ФСП ID",
    "fsp_not_found": "Протоколы ФСП не найдены",
    "survey_required": "Сначала пройдите опрос: выберите специализацию",
    "grade_locked": "Подтверждённый грейд пока нельзя менять",
    "too_young": "Регистрация открыта с 15 лет",
    "decline_pause": "Кандидат отклонил приглашение этой компании: повторно — через 30 дней",
    "retake_cooldown": "Пересдача доступна позже",
    "question_bank_empty": "Не хватает заданий для теста",
    "session_closed": "Сессия теста уже завершена",
    "session_expired": "Время сессии истекло",
    "item_token_invalid": "Задание не принадлежит этой сессии",
    "offer_closed": "Приглашение уже обработано",
    "offer_expired": "Срок приглашения истёк",
    "contacts_hidden": "Контакты откроются после согласия кандидата",
    "salary_required": "Укажите зарплатную вилку от и до",
    "need_not_found": "Потребность не найдена",
    "contacts_revoked": "Кандидат закрыл контакты для вашей компании",
    "task_closed": "Задание закрыто или срок сдачи прошёл",
    "task_answered": "Ответ на это задание уже отправлен",
    "fsp_ticket_invalid": "Вход через ФСП ID устарел: начните вход заново",
    "invites_paused": "Приглашения приостановлены до проверки",
    "complaint_duplicate": "Жалоба на это приглашение или вакансию уже отправлена",
    "demo_protected": "Демо-аккаунт: пароль и удаление закрыты, чтобы жюри могло войти",
}


class ApiError(HTTPException):
    """HTTPException with a stable machine-readable code."""

    def __init__(self, status_code: int, code: str, message: str | None = None, details: Any = None,
                 headers: dict[str, str] | None = None) -> None:
        if code not in ERROR_CODES:
            raise ValueError(f"Unregistered API error code: {code}")
        super().__init__(status_code=status_code, detail=message or ERROR_CODES[code], headers=headers)
        self.code = code
        self.details = details


def error_body(code: str, message: str, details: Any = None, detail: Any = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details},
            "detail": message if detail is None else detail}


def _jsonable_errors(errors: list[dict]) -> list[dict]:
    out = []
    for e in errors:
        item = {"loc": list(e.get("loc", ())), "msg": e.get("msg", ""), "type": e.get("type", "")}
        out.append(item)
    return out


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(StarletteHTTPException)
    async def http_error(request: Request, exc: StarletteHTTPException):
        code = getattr(exc, "code", None) or STATUS_CODES.get(exc.status_code, f"http_{exc.status_code}")
        message = exc.detail if isinstance(exc.detail, str) else ERROR_CODES.get(code, "Ошибка")
        details = getattr(exc, "details", None)
        if details is None and not isinstance(exc.detail, str):
            details = exc.detail
        headers = dict(exc.headers or {})
        if exc.status_code == 429:
            headers.setdefault("Retry-After", "60")
        return JSONResponse(status_code=exc.status_code, content=error_body(code, message, details),
                            headers=headers or None)

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        errors = _jsonable_errors(exc.errors())
        first = errors[0]["msg"] if errors else "Проверьте поля запроса"
        return JSONResponse(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                            content=error_body("validation_error", first, errors, detail=errors))

    @app.exception_handler(Exception)
    async def unhandled(request: Request, exc: Exception):
        logger.exception("Unhandled error on %s %s", request.method, request.url.path)
        return JSONResponse(status_code=500, content=error_body("internal_error", "Внутренняя ошибка сервера"))
