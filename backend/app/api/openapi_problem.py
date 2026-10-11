"""Errors leave the app as application/problem+json (RFC 9457); the OpenAPI document says the same.

FastAPI writes every declared response under application/json. Client generators and strict
clients then expect the wrong Content-Type for 4xx/5xx (ST-OAS-03). This hook renames the media
type for every error response once, when the document is first built.
"""
from __future__ import annotations

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

PROBLEM = "application/problem+json"


def problem_media(document: dict) -> dict:
    for item in document.get("paths", {}).values():
        for op in item.values():
            if not isinstance(op, dict):
                continue
            for code, response in (op.get("responses") or {}).items():
                if not str(code).isdigit() or int(code) < 400:
                    continue
                content = response.get("content") or {}
                if "application/json" in content and PROBLEM not in content:
                    content[PROBLEM] = content.pop("application/json")
                if str(code) == "429":
                    response.setdefault("headers", {})["Retry-After"] = {
                        "description": "Через сколько секунд повторить (RFC 9110 §10.2.3)",
                        "schema": {"type": "integer"}}
    return document


def install_problem_openapi(app: FastAPI) -> None:
    def build() -> dict:
        if app.openapi_schema is None:
            app.openapi_schema = problem_media(get_openapi(
                title=app.title, version=app.version, openapi_version=app.openapi_version,
                summary=app.summary, description=app.description, routes=app.routes,
                tags=app.openapi_tags, servers=app.servers, contact=app.contact,
                license_info=app.license_info, terms_of_service=app.terms_of_service,
                webhooks=app.webhooks.routes, separate_input_output_schemas=app.separate_input_output_schemas))
        return app.openapi_schema
    app.openapi = build
