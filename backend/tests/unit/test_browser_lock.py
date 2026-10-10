from fastapi.testclient import TestClient

from app.main import app


def test_health_locks_the_camera_and_marks_the_content_type():
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    assert response.headers["permissions-policy"] == "camera=(), microphone=(), geolocation=()"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
