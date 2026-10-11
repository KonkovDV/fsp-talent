"""RT-01: a NUL byte in the query or path must give 422, not a database 500."""
import asyncio

from app.core.body_limit import LimitRequestBody


def _run(path: str, query: bytes) -> list[dict]:
    sent: list[dict] = []
    reached: list[bool] = []

    async def inner(scope, receive, send):
        reached.append(True)
        await send({"type": "http.response.start", "status": 200, "headers": []})

    async def receive():
        return {"type": "http.request", "body": b"", "more_body": False}

    async def send(message):
        sent.append(message)

    scope = {"type": "http", "path": path, "query_string": query, "headers": []}
    asyncio.run(LimitRequestBody(inner)(scope, receive, send))
    return sent if not reached else [{"status": 200}]


def test_nul_in_query_is_422():
    assert _run("/api/v1/public/leaderboard", b"discipline=%00")[0]["status"] == 422
    assert _run("/x", b"a=b%00c")[0]["status"] == 422


def test_nul_in_path_is_422():
    assert _run("/api/v1/legal/documents/a\x00b", b"")[0]["status"] == 422


def test_clean_request_passes():
    assert _run("/api/v1/public/leaderboard", b"discipline=icpc&q=%D0%B0")[0]["status"] == 200
