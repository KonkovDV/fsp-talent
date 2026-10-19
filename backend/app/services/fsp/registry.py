"""HTTP client of the FSP registry (FSP_MODE=real).

The case gives no API on purpose and asks the team to decide what to request. This is the contract we
propose to the Federation (docs/FSP_INTEGRATION.md): one read-only method, the participant's protocol lines.
Nothing else is requested: no gender, no contacts, no documents.

    GET {FSP_API_URL}/participants/{fsp_id}
    Authorization: Bearer {FSP_API_KEY}

    200 {"fsp_id": "FSP001", "display_name": "...", "region": "...", "birth_date": "2003-05-12",
         "results": [{"event_id": "...", "event_name": "...", "discipline": "algorithmic",
                      "competition_status": "russia_championship", "place": 3, "total_participants": 180,
                      "is_team": false, "team_size": 1, "event_date": "2025-11-20", "regions_count": 52,
                      "role": "participant", "protocol_url": "https://..."}],
         "ranks": [{"discipline": "algorithmic", "rank": "КМС", "assigned_at": "2025-11-20",
                    "order_ref": "Приказ-12"}]}
    404 the participant is not in the registry
"""
from __future__ import annotations

import re
from datetime import UTC, date, datetime

import httpx

from app.core.config import settings
from app.services.fsp.mock import FSPChanges, FSPParticipant, FSPResult, RegistryRank

DISCIPLINES = {"algorithmic", "product", "security", "bas", "robotics", "ai"}
REGISTRY_RANKS = {"МС", "КМС", "I", "II", "III", "I юн.", "II юн.", "III юн."}
# One path segment. The id is placed in the registry URL next to the access key.
_REGISTRY_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]{0,63}$")


def registry_id(value: object) -> str | None:
    """An id the registry client may put in a path. Anything else is refused before the request."""
    if isinstance(value, bool) or not isinstance(value, (str, int)):
        return None
    text = str(value).strip()
    if _REGISTRY_ID.fullmatch(text) is None:
        return None
    return text


class FSPRegistryError(Exception):
    """The registry answered with something other than a participant or 404."""


def _http_url(value: object) -> str | None:
    """A protocol link is only a web address. Anything else is dropped before it can be stored."""
    if not isinstance(value, str):
        return None
    url = value.strip()
    scheme = url.split(":", 1)[0].lower()
    if scheme in {"http", "https"} and "://" in url[:8].lower():
        return url[:500]
    return None


def _result(row: dict) -> FSPResult | None:
    if row.get("discipline") not in DISCIPLINES:
        return None   # an unknown discipline is skipped, not guessed
    place, total = int(row["place"]), int(row["total_participants"])
    if not 1 <= place <= total:
        return None
    return FSPResult(
        event_id=str(row["event_id"]), event_name=str(row["event_name"]), discipline=row["discipline"],
        competition_status=str(row["competition_status"]), place=place, total_participants=total,
        is_team=bool(row.get("is_team", False)), team_size=max(1, int(row.get("team_size") or 1)),
        event_date=date.fromisoformat(row["event_date"]), regions_count=row.get("regions_count"),
        role=str(row.get("role") or "participant"), protocol_url=_http_url(row.get("protocol_url")),
        ekp_number=(str(row["ekp_number"]) if row.get("ekp_number") else None),
    )


def _rank(row: dict) -> RegistryRank | None:
    if row.get("discipline") not in DISCIPLINES or row.get("rank") not in REGISTRY_RANKS:
        return None
    return RegistryRank(row["discipline"], row["rank"], date.fromisoformat(row["assigned_at"]),
                        str(row.get("order_ref") or ""))


def parse_participant(payload: dict) -> FSPParticipant:
    results = [r for r in (_result(row) for row in payload.get("results", [])) if r is not None]
    ranks = [r for r in (_rank(row) for row in payload.get("ranks", [])) if r is not None]
    return FSPParticipant(
        fsp_id=str(payload["fsp_id"]), display_name=str(payload.get("display_name") or ""),
        region=str(payload.get("region") or ""), birth_date=date.fromisoformat(payload["birth_date"]),
        results=results, ranks=ranks, complete=payload.get("complete") is True,
    )


class HttpFSPAdapter:
    def __init__(self, http: httpx.AsyncClient | None = None):
        self._http = http

    async def fetch_participant(self, fsp_id: str) -> FSPParticipant | None:
        if not settings.FSP_API_URL:
            raise FSPRegistryError("FSP_API_URL is not set")
        safe = registry_id(fsp_id)
        if safe is None:
            raise FSPRegistryError("registry id")
        client = self._http or httpx.AsyncClient(timeout=10)
        try:
            response = await client.get(f"{settings.FSP_API_URL.rstrip('/')}/participants/{safe}",
                                        headers={"Authorization": f"Bearer {settings.FSP_API_KEY}",
                                                 "Accept": "application/json"})
        except httpx.HTTPError as e:
            raise FSPRegistryError("registry unreachable") from e
        finally:
            if self._http is None:
                await client.aclose()
        if response.status_code == 404:
            return None
        if response.status_code != 200:
            raise FSPRegistryError(f"registry answered {response.status_code}")
        try:
            return parse_participant(response.json())
        except (KeyError, TypeError, ValueError) as e:
            raise FSPRegistryError("registry payload does not match the contract") from e

    async def changes_since(self, since: datetime) -> FSPChanges:
        if not settings.FSP_API_URL:
            raise FSPRegistryError("FSP_API_URL is not set")
        client = self._http or httpx.AsyncClient(timeout=10)
        try:
            response = await client.get(
                f"{settings.FSP_API_URL.rstrip('/')}/participants/changes",
                params={"since": since.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")},
                headers={"Authorization": f"Bearer {settings.FSP_API_KEY}", "Accept": "application/json"},
            )
        except httpx.HTTPError as e:
            raise FSPRegistryError("registry unreachable") from e
        finally:
            if self._http is None:
                await client.aclose()
        if response.status_code != 200:
            raise FSPRegistryError(f"registry answered {response.status_code}")
        try:
            payload = response.json()
            ids = [item for raw in payload.get("fsp_ids", []) if (item := registry_id(raw))]
            nxt = payload.get("next_since")
            moment = datetime.fromisoformat(nxt.replace("Z", "+00:00")) if nxt else datetime.now(UTC)
            return FSPChanges(ids, moment)
        except (AttributeError, TypeError, ValueError) as e:
            raise FSPRegistryError("registry payload does not match the contract") from e
