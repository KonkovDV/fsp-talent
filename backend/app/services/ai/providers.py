"""Which language model the platform calls, switchable at runtime from the moderation desk.

Only providers listed in KINDS exist: their hosts are fixed here, the desk never takes a URL.
All four are Russian clouds. The stored key is sealed with AES-GCM and never returned by the API.
Before a call the host must resolve to public addresses only, and redirects are refused.
Every user message passes through `for_model`. Known patterns are removed.
That does not prove the remaining text is anonymous.

The model reads résumé text for skills with quotes and writes test drafts for a human.
It never ranks candidates: the match score stays the decomposable sum in services/matching.py.
"""
import asyncio
import ipaddress
import logging
import re
import socket
import time
import weakref
from dataclasses import dataclass, field

import httpx

from app.core.config import settings

logger = logging.getLogger(__name__)

TIMEOUT = 30.0
HTTP_TIMEOUT = httpx.Timeout(60.0, connect=5.0)
CONNECT_ATTEMPTS = 3
CACHE_SECONDS = 30.0
_MODEL = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:/-]{0,99}$")
_PARAM = re.compile(r"^[a-z0-9][a-z0-9-]{0,62}$")
_SCOPES = ("GIGACHAT_API_PERS", "GIGACHAT_API_B2B", "GIGACHAT_API_CORP")


@dataclass(frozen=True)
class Kind:
    label: str
    hosts: tuple[str, ...]
    params: tuple[str, ...]
    hint: str


KINDS: dict[str, Kind] = {
    "gigachat": Kind("GigaChat (Сбер)", ("ngw.devices.sberbank.ru", "gigachat.devices.sberbank.ru"), ("scope",),
                     "Ключ авторизации из личного кабинета GigaChat API"),
    "yandex": Kind("YandexGPT (Yandex AI Studio)", ("llm.api.cloud.yandex.net",), ("folder_id",),
                   "API-ключ сервисного аккаунта с ролью ai.languageModels.user; модель вида yandexgpt-5.1/latest"),
    "cloudru": Kind("Cloud.ru Foundation Models", ("foundation-models.api.cloud.ru",), (),
                    "API-ключ сервисного аккаунта для Foundation Models; модель вида ai-sage/GigaChat3-10B-A1.8B"),
    "mws": Kind("MWS GPT (МТС)", ("gpt.mwsapis.ru",), ("project",),
                "API-ключ аккаунта с ролью gpt.inferencer; модель — идентификатор деплоймента"),
}


@dataclass(frozen=True)
class Provider:
    kind: str
    model: str
    check_model: str | None
    secret: str
    params: dict = field(default_factory=dict)
    source: str = "env"
    id: str | None = None


class ProviderError(RuntimeError):
    """The call was refused before leaving the server, or the provider answered with an error."""


def validate(kind: str, model: str, check_model: str | None, params: dict, secret: str) -> dict:
    """Clean parameters for a new provider, or ValueError with a message for the desk."""
    if kind not in KINDS:
        raise ValueError("Такого провайдера нет в списке")
    for name, value in (("Модель", model), ("Проверяющая модель", check_model)):
        if value is not None and not _MODEL.match(value):
            raise ValueError(f"{name}: латиница, цифры и . _ : / -, до 100 знаков")
    if check_model and check_model == model:
        raise ValueError("Проверяющая модель должна отличаться от основной")
    if not secret or len(secret) > 2000 or any(c.isspace() for c in secret):
        raise ValueError("Ключ пустой, слишком длинный или с пробелами")
    clean: dict[str, str] = {}
    for name in KINDS[kind].params:
        value = str((params or {}).get(name) or "").strip()
        if name == "scope":
            value = value or "GIGACHAT_API_PERS"
            if value not in _SCOPES:
                raise ValueError("Scope GigaChat: GIGACHAT_API_PERS, GIGACHAT_API_B2B или GIGACHAT_API_CORP")
        elif not _PARAM.match(value):
            raise ValueError(f"{name}: строчная латиница, цифры и дефис, до 63 знаков")
        clean[name] = value
    return clean


def _env() -> Provider | None:
    if settings.GIGACHAT_CREDENTIALS:
        return Provider("gigachat", settings.GIGACHAT_MODEL, settings.GIGACHAT_CHECK_MODEL or None,
                        settings.GIGACHAT_CREDENTIALS, {"scope": settings.GIGACHAT_SCOPE})
    if settings.YANDEX_API_KEY and settings.YANDEX_FOLDER_ID:
        try:
            params = validate("yandex", settings.YANDEX_MODEL, settings.YANDEX_CHECK_MODEL or None,
                              {"folder_id": settings.YANDEX_FOLDER_ID}, settings.YANDEX_API_KEY)
        except ValueError as exc:
            logger.error("YANDEX_* settings are ignored: %s", exc)
            return None
        return Provider("yandex", settings.YANDEX_MODEL, settings.YANDEX_CHECK_MODEL or None,
                        settings.YANDEX_API_KEY, params)
    return None


_stored: Provider | None = None
_loaded_at: float | None = None


def active() -> Provider | None:
    """The provider in use: the one switched on at the desk, otherwise GigaChat from the environment."""
    if not settings.AI_ENABLED:
        return None
    return _stored or _env()


def forget() -> None:
    global _stored, _loaded_at
    _stored, _loaded_at = None, None
    _clients.clear()


async def _active_row(db):
    from sqlalchemy import select

    from app.models.ai_provider import AiProvider
    query = select(AiProvider).where(AiProvider.is_active.is_(True))
    if db is not None:
        return await db.scalar(query)
    from app.core.database import AsyncSessionLocal
    async with AsyncSessionLocal() as own:
        return await own.scalar(query)


async def refresh(db=None, *, force: bool = False) -> Provider | None:
    """Reload the active row at most every 30 seconds. A database error keeps the last known choice."""
    global _stored, _loaded_at
    if not settings.AI_ENABLED:
        return None
    if not force and _loaded_at is not None and time.monotonic() - _loaded_at < CACHE_SECONDS:
        return active()
    from app.models.ai_provider import open_secret
    _loaded_at = time.monotonic()
    try:
        row = await _active_row(db)
        _stored = None if row is None else Provider(
            row.kind, row.model, row.check_model, open_secret(row), dict(row.params or {}), "db", str(row.id))
    except Exception:
        logger.exception("AI provider settings were not read, the previous choice stays")
    return active()


def _public_only(host: str) -> None:
    try:
        infos = socket.getaddrinfo(host, 443, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise ProviderError(f"{host} не резолвится") from exc
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        mapped = getattr(address, "ipv4_mapped", None)
        if not (mapped or address).is_global:
            raise ProviderError(f"{host} указывает на внутренний адрес")


async def check_hosts(kind: str) -> None:
    for host in KINDS[kind].hosts:
        await asyncio.to_thread(_public_only, host)


def request_for(provider: Provider, model: str) -> tuple[str, dict[str, str], str]:
    """URL, headers and the model name in the provider's own form. Hosts come from KINDS only."""
    if provider.kind == "yandex":
        return ("https://llm.api.cloud.yandex.net/v1/chat/completions",
                {"Authorization": f"Api-Key {provider.secret}", "x-data-logging-enabled": "false"},
                f"gpt://{provider.params['folder_id']}/{model}")
    if provider.kind == "cloudru":
        return ("https://foundation-models.api.cloud.ru/v1/chat/completions",
                {"Authorization": f"Bearer {provider.secret}"}, model)
    if provider.kind == "mws":
        return (f"https://gpt.mwsapis.ru/projects/{provider.params['project']}/openai/v1/chat/completions",
                {"Authorization": f"Bearer {provider.secret}"}, model)
    raise ProviderError("У этого провайдера нет OpenAI-совместимого адреса")


async def _gigachat(provider: Provider, model: str, messages: list[dict], temperature: float) -> str:
    from gigachat import GigaChat

    giga = GigaChat(credentials=provider.secret, scope=provider.params.get("scope", "GIGACHAT_API_PERS"),
                    model=model, verify_ssl_certs=settings.GIGACHAT_VERIFY_SSL, timeout=TIMEOUT)
    try:
        resp = await giga.achat({"messages": messages, "temperature": temperature})
    finally:
        close = getattr(giga, "aclose", None)
        if close:
            await close()
    return str(resp.choices[0].message.content or "")


_clients: "weakref.WeakKeyDictionary[asyncio.AbstractEventLoop, httpx.AsyncClient]" = weakref.WeakKeyDictionary()


def _client() -> httpx.AsyncClient:
    """One pooled client per event loop: a kept-alive TLS connection is not renegotiated for each call."""
    loop = asyncio.get_running_loop()
    client = _clients.get(loop)
    if client is None or client.is_closed:
        client = httpx.AsyncClient(timeout=HTTP_TIMEOUT, follow_redirects=False, trust_env=False,
                                   limits=httpx.Limits(max_connections=20, keepalive_expiry=60.0))
        _clients[loop] = client
    return client


async def _openai_compatible(provider: Provider, model: str, messages: list[dict], temperature: float) -> str:
    url, headers, wire_model = request_for(provider, model)
    host = KINDS[provider.kind].hosts[0]
    body = {"model": wire_model, "messages": messages, "temperature": temperature}
    client = _client()
    for attempt in range(CONNECT_ATTEMPTS):
        try:
            resp = await client.post(url, headers=headers, json=body)
            break
        except (httpx.ConnectError, httpx.ConnectTimeout):
            # Only connection errors: nothing reached the provider, so the prompt cannot run twice.
            if attempt == CONNECT_ATTEMPTS - 1:
                raise ProviderError(f"{host} не отвечает на соединение") from None
    if resp.status_code != 200:
        raise ProviderError(f"{host} ответил {resp.status_code}")
    try:
        return str(resp.json()["choices"][0]["message"]["content"] or "")
    except (ValueError, KeyError, IndexError, TypeError) as exc:
        raise ProviderError(f"{host} прислал ответ не по схеме") from exc


async def chat(provider: Provider, model: str, system: str, user: str, *, temperature: float = 0.0,
               limit: int = 8000) -> str:
    from app.services.ai.assistant import for_model

    if provider.kind not in KINDS:
        raise ProviderError("Такого провайдера нет в списке")
    await check_hosts(provider.kind)
    messages = [{"role": "system", "content": system}, {"role": "user", "content": for_model(user)[:limit]}]
    if provider.kind == "gigachat":
        return await _gigachat(provider, model, messages, temperature)
    return await _openai_compatible(provider, model, messages, temperature)
