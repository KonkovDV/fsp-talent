"""One public page into the need draft. Nothing is saved.

Redirects are not followed. A host that is not a public address is refused.
There is no special case for a job board and no bypass of its checks.
"""
from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import urlsplit

import httpx

_TAG = re.compile(r"(?is)<(script|style)[\s\S]*?</\1>|<[^>]+>")
_SPACE = re.compile(r"\s+")


class PageDraftError(Exception):
    pass


def page_text(html: str) -> str:
    return _SPACE.sub(" ", _TAG.sub(" ", html)).strip()[:8000]


def public_host(host: str) -> None:
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None and not literal.is_global:
        raise PageDraftError("Адрес страницы не публичный")
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise PageDraftError("Адрес страницы не открывается") from exc
    for info in infos:
        address = ipaddress.ip_address(info[4][0])
        mapped = getattr(address, "ipv4_mapped", None)
        if not (mapped or address).is_global:
            raise PageDraftError("Адрес страницы не публичный")


async def fetch_page(url: str) -> str:
    parts = urlsplit(url.strip())
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise PageDraftError("Нужна ссылка http или https")
    public_host(parts.hostname)
    try:
        async with httpx.AsyncClient(timeout=8.0, follow_redirects=False) as client:
            response = await client.get(url.strip(), headers={"User-Agent": "FSP-Talent draft"})
    except httpx.HTTPError as exc:
        raise PageDraftError("Страница не открылась") from exc
    if response.status_code != 200:
        raise PageDraftError("Страница не открылась")
    if len(response.content) > 500_000:
        raise PageDraftError("Страница слишком большая")
    kind = response.headers.get("content-type", "")
    if kind and "html" not in kind and "text" not in kind:
        raise PageDraftError("Нужна текстовая страница")
    text = page_text(response.text)
    if len(text) < 10:
        raise PageDraftError("На странице слишком мало текста")
    return text
