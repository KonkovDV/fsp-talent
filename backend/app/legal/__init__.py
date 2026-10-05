"""Versioned legal documents shipped with the code.

The text of each document lives in app/legal/docs/<kind>.md with a small front matter block. A consent row
stores kind + version + SHA-256 of the exact body, so it is provable later which text the person accepted,
even after the document is edited (a new text must get a new version; a unit test checks the hash is stable).
"""
from __future__ import annotations

import hashlib
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

DOCS_DIR = Path(__file__).parent / "docs"


@dataclass(frozen=True)
class LegalDocument:
    kind: str
    version: str
    title: str
    roles: tuple[str, ...]
    required: bool
    body_md: str
    sha256: str


def _parse(path: Path) -> LegalDocument:
    raw = path.read_text(encoding="utf-8")
    if not raw.startswith("---\n"):
        raise ValueError(f"{path.name}: front matter is missing")
    head, body = raw[4:].split("\n---\n", 1)
    meta: dict[str, str] = {}
    for line in head.splitlines():
        key, _, value = line.partition(":")
        meta[key.strip()] = value.strip().strip('"')
    body = body.lstrip("\n")
    return LegalDocument(
        kind=meta["kind"], version=meta["version"], title=meta["title"],
        roles=tuple(r.strip() for r in meta["roles"].split(",") if r.strip()),
        required=meta.get("required", "false").lower() == "true",
        body_md=body, sha256=hashlib.sha256(body.encode("utf-8")).hexdigest(),
    )


@lru_cache
def documents() -> dict[str, LegalDocument]:
    docs = {}
    for path in sorted(DOCS_DIR.glob("*.md")):
        doc = _parse(path)
        if doc.kind != path.stem:
            raise ValueError(f"{path.name}: kind {doc.kind!r} must match the file name")
        docs[doc.kind] = doc
    return docs


def get_document(kind: str) -> LegalDocument | None:
    return documents().get(kind)


def required_kinds(role: str) -> list[str]:
    return [d.kind for d in documents().values() if d.required and role in d.roles]
