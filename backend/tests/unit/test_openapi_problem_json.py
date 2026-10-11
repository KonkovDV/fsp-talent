"""ST-OAS-03: every error response in the OpenAPI document is application/problem+json, like the wire."""
from app.main import app


def _errors():
    for item in app.openapi()["paths"].values():
        for op in item.values():
            if isinstance(op, dict):
                for code, response in (op.get("responses") or {}).items():
                    if code.isdigit() and int(code) >= 400:
                        yield code, response


def test_error_responses_are_problem_json():
    seen = 0
    for _code, response in _errors():
        content = response.get("content") or {}
        assert "application/json" not in content
        if content:
            assert "application/problem+json" in content
            seen += 1
    assert seen > 100


def test_success_responses_stay_json_and_429_names_retry_after():
    ok = app.openapi()["paths"]["/api/v1/candidates/me"]["get"]["responses"]["200"]
    assert "application/json" in ok["content"]
    assert all("Retry-After" in r.get("headers", {}) for c, r in _errors() if c == "429")


def test_wire_errors_use_the_same_media_type():
    from fastapi.testclient import TestClient
    r = TestClient(app).get("/api/v1/candidates/me")
    assert r.status_code == 401 and r.headers["content-type"].startswith("application/problem+json")
