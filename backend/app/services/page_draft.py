"""One public page into the need draft. Nothing is saved.

Redirects are not followed. The connection uses an address that already passed the
public check, so a later DNS answer cannot point the same name inside.
There is no special case for a job board and no bypass of its checks.
"""
from __future__ import annotations

import ipaddress
import re
import socket
from urllib.parse import urlsplit, urlunsplit

import httpx

_SCRIPT = re.compile(r"(?is)<(script|style)\b[^>]*>[\s\S]*?</\1>|<(script|style)\b[^>]*>[\s\S]*")
_TAG = re.compile(r"(?is)<[^>]+>")
_SPACE = re.compile(r"\s+")
_MAX_BODY = 500_000


class PageDraftError(Exception):
    pass


class _Pinned(httpx.AsyncHTTPTransport):
    """Connect to the checked address. The name stays on the Host header and on the certificate."""

    def __init__(self, hostname: str, ip: str):
        super().__init__(retries=0)
        self._hostname = hostname
        self._ip = ip

    async def handle_async_request(self, request: httpx.Request) -> httpx.Response:
        request.extensions["sni_hostname"] = self._hostname
        request.url = request.url.copy_with(host=self._ip)
        return await super().handle_async_request(request)


def page_text(html: str) -> str:
    return _SPACE.sub(" ", _TAG.sub(" ", _SCRIPT.sub(" ", html))).strip()[:8000]


def _global(address: ipaddress.IPv4Address | ipaddress.IPv6Address) -> ipaddress.IPv4Address | ipaddress.IPv6Address:
    mapped = getattr(address, "ipv4_mapped", None)
    return mapped or address


def public_ip(host: str) -> str:
    """One public address. Any private answer for the same name refuses the page."""
    try:
        literal = ipaddress.ip_address(host)
    except ValueError:
        literal = None
    if literal is not None:
        check = _global(literal)
        if not check.is_global:
            raise PageDraftError("Адрес страницы не публичный")
        return str(check)
    try:
        infos = socket.getaddrinfo(host, None, type=socket.SOCK_STREAM)
    except OSError as exc:
        raise PageDraftError("Адрес страницы не открывается") from exc
    chosen: str | None = None
    for info in infos:
        check = _global(ipaddress.ip_address(info[4][0]))
        if not check.is_global:
            raise PageDraftError("Адрес страницы не публичный")
        if chosen is None:
            chosen = str(check)
    if chosen is None:
        raise PageDraftError("Адрес страницы не открывается")
    return chosen


def public_host(host: str) -> None:
    public_ip(host)


def _clean_url(parts) -> str:
    host = parts.hostname or ""
    if ":" in host:
        host = f"[{host}]"
    netloc = f"{host}:{parts.port}" if parts.port else host
    return urlunsplit((parts.scheme, netloc, parts.path or "/", parts.query, ""))


async def fetch_page(url: str) -> str:
    parts = urlsplit(url.strip())
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise PageDraftError("Нужна ссылка http или https")
    ip = public_ip(parts.hostname)
    try:
        async with httpx.AsyncClient(
            transport=_Pinned(parts.hostname, ip), timeout=8.0, follow_redirects=False, trust_env=False,
        ) as client:
            async with client.stream("GET", _clean_url(parts), headers={"User-Agent": "FSP-Talent draft"}) as response:
                if response.status_code != 200:
                    raise PageDraftError("Страница не открылась")
                kind = response.headers.get("content-type", "")
                if kind and "html" not in kind.lower() and "text" not in kind.lower():
                    raise PageDraftError("Нужна текстовая страница")
                buf = bytearray()
                async for chunk in response.aiter_bytes():
                    if len(buf) + len(chunk) > _MAX_BODY:
                        raise PageDraftError("Страница слишком большая")
                    buf.extend(chunk)
    except PageDraftError:
        raise
    except httpx.HTTPError as exc:
        raise PageDraftError("Страница не открылась") from exc
    text = page_text(buf.decode("utf-8", errors="replace"))
    if len(text) < 10:
        raise PageDraftError("На странице слишком мало текста")
    return text
