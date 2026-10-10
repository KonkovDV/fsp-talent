"""did:web for the site host. The key is the same Ed25519 key that signs credentials.

The credential issuer id stays a URL. This document only publishes that key under did:web.
"""
from __future__ import annotations

from urllib.parse import urlsplit


def did_web_id(base_url: str) -> str:
    parts = urlsplit(base_url if "://" in base_url else f"https://{base_url}")
    host = parts.hostname or "localhost"
    if parts.port and parts.port not in (80, 443):
        host = f"{host}%3A{parts.port}"
    return "did:web:" + host


def did_document(base_url: str, multibase: str) -> dict:
    did = did_web_id(base_url)
    key = f"{did}#key-1"
    return {
        "@context": [
            "https://www.w3.org/ns/did/v1",
            "https://w3id.org/security/multikey/v1",
        ],
        "id": did,
        "verificationMethod": [{
            "id": key,
            "type": "Multikey",
            "controller": did,
            "publicKeyMultibase": multibase,
        }],
        "assertionMethod": [key],
    }
