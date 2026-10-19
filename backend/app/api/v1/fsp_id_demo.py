"""Demo FSP ID provider: stands in for the Keycloak login page of the Federation (FSP_ID_MODE=mock).

It exists so the full OIDC code flow can be shown without the real FSP ID. The page at /fsp-id/authorize
says it is a demo; in production this router is off and the browser goes to the Keycloak realm instead.
"""
from __future__ import annotations

from urllib.parse import urlencode

from fastapi import APIRouter
from pydantic import BaseModel, Field

from app.api.errors import ApiError
from app.core.config import settings
from app.core.ratelimit import too_many
from app.services.fsp.identity import FspIdError, MockFspIdProvider
from app.services.fsp.mock import MockFSPAdapter

router = APIRouter(prefix="/fsp-id-demo", tags=["fsp-id-demo"])


class DemoLoginIn(BaseModel):
    fsp_id: str = Field(min_length=3, max_length=64)
    password: str = Field(min_length=1, max_length=200)
    client_id: str = Field(max_length=100)
    redirect_uri: str = Field(max_length=500)
    state: str = Field(min_length=8, max_length=200)
    code_challenge: str = Field(min_length=43, max_length=128)
    code_challenge_method: str = Field(pattern="^S256$")
    nonce: str | None = Field(default=None, min_length=8, max_length=200)


@router.post("/login")
async def demo_login(body: DemoLoginIn):
    """Check the demo registry (FSP2000–FSP2099, password test) and send the browser back with a code."""
    if settings.FSP_ID_MODE != "mock":
        raise ApiError(404, "not_found")
    fsp_id = body.fsp_id.strip().upper()
    if await too_many(f"fsp-id-demo:{fsp_id}", limit=10):
        raise ApiError(429, "rate_limited")
    if not await MockFSPAdapter().verify_secret(fsp_id, body.password):
        raise ApiError(400, "fsp_invalid")
    try:
        code = await MockFspIdProvider().issue_code(
            fsp_id, body.client_id, body.redirect_uri, body.code_challenge, nonce=body.nonce)
    except FspIdError as e:
        raise ApiError(400, "validation_error", "Неизвестный клиент или адрес возврата") from e
    return {"redirect_to": f"{body.redirect_uri}?{urlencode({'code': code, 'state': body.state})}"}
