from fastapi import FastAPI
from fastapi.testclient import TestClient

from app.api.errors import ERROR_CODES, ApiError, install_error_handlers
from app.api.problems import CLASSES, CODE_CLASS, catalog


def test_every_code_belongs_to_one_of_twenty_classes():
    assert set(CODE_CLASS) == set(ERROR_CODES)
    assert set(CLASSES) == {f"E{n:02d}" for n in range(1, 21)}
    assert set(CODE_CLASS.values()) == set(CLASSES)
    assert len(catalog()) == 20


def test_an_error_is_problem_json_and_keeps_the_old_fields():
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/needs/missing")
    def missing():
        raise ApiError(404, "need_not_found")

    response = TestClient(app).get("/needs/missing")
    assert response.headers["content-type"].startswith("application/problem+json")
    body = response.json()
    assert body["problem"] == "E03" and body["type"] == "/problems/E03"
    assert body["status"] == 404 and body["instance"] == "/needs/missing"
    assert body["error"]["code"] == "need_not_found"
    assert body["detail"] == body["error"]["message"]
