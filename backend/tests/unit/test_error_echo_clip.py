"""RT-02: a 20 KB path or field must not come back as a 20 KB error body."""
import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.errors import ECHO_LIMIT, install_error_handlers


def _client() -> TestClient:
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/items/{item_id}")
    async def item(item_id: uuid.UUID):
        return {}

    return TestClient(app)


def test_long_path_is_clipped_in_422():
    r = _client().get("/items/" + "A" * 20000)
    assert r.status_code == 422
    assert len(r.content) < 3000
    assert len(r.json()["instance"]) <= ECHO_LIMIT + 1


def test_long_path_is_clipped_in_404():
    r = _client().get("/nope/" + "B" * 20000)
    assert r.status_code == 404
    assert len(r.content) < 3000


def test_short_values_unchanged():
    r = _client().get("/items/x")
    assert r.json()["instance"] == "/items/x"
