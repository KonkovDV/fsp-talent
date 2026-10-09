"""Refuse a request body above 10 MB with 413.

Caddy's own limit closes the TLS connection, so the client never sees a status.
The check uses Content-Length when the client sent one, and otherwise counts the
bytes as they arrive, before the route runs.
"""
from __future__ import annotations

import json

from app.api.errors import error_body

MAX_BODY_BYTES = 10 * 1024 * 1024


class LimitRequestBody:
    def __init__(self, app, max_bytes: int = MAX_BODY_BYTES):
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        length = _content_length(scope)
        if length is not None and length > self.max_bytes:
            await _reject(send)
            return
        if length is not None:
            await self.app(scope, receive, send)
            return
        chunks: list[dict] = []
        total = 0
        while True:
            message = await receive()
            if message["type"] == "http.request":
                total += len(message.get("body") or b"")
                if total > self.max_bytes:
                    await _reject(send)
                    return
            chunks.append(message)
            if message["type"] != "http.request" or not message.get("more_body"):
                break
        index = 0

        async def replay():
            nonlocal index
            if index < len(chunks):
                message = chunks[index]
                index += 1
                return message
            return {"type": "http.request", "body": b"", "more_body": False}

        await self.app(scope, replay, send)


def _content_length(scope) -> int | None:
    for key, value in scope.get("headers") or []:
        if key.lower() == b"content-length":
            try:
                return int(value)
            except ValueError:
                return None
    return None


async def _reject(send) -> None:
    payload = json.dumps(
        error_body("payload_too_large", "Тело запроса больше 10 МБ"),
        ensure_ascii=False,
    ).encode()
    await send({
        "type": "http.response.start",
        "status": 413,
        "headers": [
            (b"content-type", b"application/json; charset=utf-8"),
            (b"content-length", str(len(payload)).encode()),
        ],
    })
    await send({"type": "http.response.body", "body": payload, "more_body": False})
