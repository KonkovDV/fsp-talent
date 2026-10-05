"""Swagger UI from our own origin, with no inline script.

The site's CSP is `script-src 'self'`. FastAPI's built-in page pulls swagger-ui from cdn.jsdelivr.net and
starts it with an inline <script>, so behind that policy /docs renders blank. Here the bundle is vendored in
app/static/swagger-ui (swagger-ui-dist 5, Apache-2.0, reads OpenAPI 3.1) and the start-up code is a separate
same-origin file.
"""
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import HTMLResponse, Response
from fastapi.staticfiles import StaticFiles

ASSETS = Path(__file__).resolve().parent.parent / "static" / "swagger-ui"

_PAGE = """<!doctype html>
<html lang="ru">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{title} — API</title>
<link rel="stylesheet" href="/docs/assets/swagger-ui.css">
</head>
<body>
<div id="swagger-ui"></div>
<script src="/docs/assets/swagger-ui-bundle.js"></script>
<script src="/docs/init.js"></script>
</body>
</html>
"""

_INIT = """window.ui = SwaggerUIBundle({
  url: '/openapi.json',
  dom_id: '#swagger-ui',
  deepLinking: true,
  persistAuthorization: false,
  validatorUrl: null,
  presets: [SwaggerUIBundle.presets.apis],
  layout: 'BaseLayout'
});
"""


def install_docs(app: FastAPI) -> None:
    app.mount("/docs/assets", StaticFiles(directory=str(ASSETS)), name="swagger-assets")

    @app.get("/docs", include_in_schema=False)
    async def swagger_page() -> HTMLResponse:
        return HTMLResponse(_PAGE.format(title=app.title))

    @app.get("/docs/init.js", include_in_schema=False)
    async def swagger_init() -> Response:
        return Response(_INIT, media_type="application/javascript")
