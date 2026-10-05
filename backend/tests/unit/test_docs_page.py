"""/docs must work behind the site CSP (script-src 'self'): no CDN, no inline script."""
import re

from fastapi.testclient import TestClient

from app.api.docs import ASSETS
from app.main import app


def test_swagger_page_has_no_inline_or_external_script():
    client = TestClient(app)
    page = client.get("/docs")
    assert page.status_code == 200
    scripts = re.findall(r"<script([^>]*)>(.*?)</script>", page.text, flags=re.S)
    assert scripts, "the page must load swagger-ui"
    for attrs, body in scripts:
        assert body.strip() == "", "inline script is blocked by the CSP"
        src = re.search(r'src="([^"]+)"', attrs).group(1)
        assert src.startswith("/"), f"external script {src} is blocked by the CSP"
    assert "cdn." not in page.text


def test_swagger_assets_are_served_locally():
    client = TestClient(app)
    assert (ASSETS / "swagger-ui-bundle.js").is_file() and (ASSETS / "LICENSE").is_file()
    assert client.get("/docs/init.js").headers["content-type"].startswith("application/javascript")
    assert client.get("/docs/assets/swagger-ui.css").status_code == 200
