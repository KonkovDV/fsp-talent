"""RT-04: a JSON body with \\u0000 must give 422, not a database 500."""
import asyncio

from app.core.body_limit import LimitRequestBody


def _run(body: bytes, ctype: bytes = b"application/json") -> int:
    status: list[int] = []
    seen: list[bytes] = []

    async def inner(scope, receive, send):
        seen.append((await receive())["body"])
        status.append(200)

    async def receive():
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(message):
        if message["type"] == "http.response.start":
            status.append(message["status"])

    headers = [(b"content-type", ctype), (b"content-length", str(len(body)).encode())]
    scope = {"type": "http", "path": "/x", "query_string": b"", "headers": headers}
    asyncio.run(LimitRequestBody(inner)(scope, receive, send))
    if status == [200]:
        assert seen == [body]
    return status[0]


def test_escaped_nul_is_422():
    assert _run(b'{"display_name":"qa\\u0000x"}') == 422
    assert _run(b'{"a":"\\U0000"}') == 422


def test_literal_backslash_u0000_text_passes():
    # The user typed a backslash, then "u0000": JSON "\\\\u0000" is not a NUL.
    assert _run(b'{"a":"\\\\u0000"}') == 200


def test_clean_json_and_multipart_pass():
    assert _run(b'{"display_name":"qa"}') == 200
    assert _run(b"--b\r\n\\u0000", b"multipart/form-data; boundary=b") == 200
