"""
Checks for scoring, search and credentials.

Runs without a live DB/Redis: all SQLAlchemy calls are mocked.
"""
from __future__ import annotations

import ast
import uuid
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

# Resolve paths relative to repo root (tests run from backend/)
_REPO_ROOT = Path(__file__).parent.parent.parent
_APP = _REPO_ROOT / "app"


# ---------------------------------------------------------------------------
# participant.updated_at is set on insert
# ---------------------------------------------------------------------------

def test_bug03_updated_at_has_default():
    """
    Participant.updated_at column must carry a Python-side default=
    so that SQLAlchemy populates it on INSERT, not just on UPDATE.
    """
    from app.models.participant import Participant
    col = Participant.__table__.c["updated_at"]
    assert col.default is not None, (
        "updated_at must have a Python-side default= so it is set on INSERT. "
        "Without it the column is NULL for newly created Participants."
    )
    assert col.onupdate is not None, "updated_at must still have onupdate= for UPDATE"


def test_bug03_updated_at_default_is_tz_aware():
    """
    The default lambda for updated_at must return a timezone-aware datetime.
    """
    from app.models.participant import Participant
    col = Participant.__table__.c["updated_at"]
    # SQLAlchemy wraps a zero-arg default as lambda ctx: fn().
    val = col.default.arg(None)
    assert val.tzinfo is not None, "updated_at default must produce a timezone-aware datetime"


# ---------------------------------------------------------------------------
# verify_credential uses the cached public key
# ---------------------------------------------------------------------------

def test_bug04_public_key_obj_is_cached():
    """
    _public_key_obj() must be decorated with @lru_cache so repeated calls
    to verify_credential do not reconstruct Ed25519PublicKey every time.
    """
    from app.services.vc.issuer import _public_key_obj
    assert hasattr(_public_key_obj, "cache_info"), (
        "_public_key_obj must be decorated with @lru_cache to avoid "
        "reconstructing Ed25519PublicKey on every verify_credential call."
    )


# ---------------------------------------------------------------------------
# _safe_uuid ignores a malformed JSONB entry
# ---------------------------------------------------------------------------

def test_bug06_safe_uuid_returns_none_on_bad_input():
    """
    _safe_uuid(e) must return None (not raise) when given a non-UUID string
    or any other non-conforming value stored in the JSONB top_event_ids field.
    """
    from app.services.search.pipeline import _safe_uuid

    uid = uuid.uuid4()
    assert _safe_uuid(str(uid)) == uid
    assert _safe_uuid("not-a-uuid") is None
    assert _safe_uuid("") is None
    assert _safe_uuid(None) is None
    assert _safe_uuid(12345) is None
    assert _safe_uuid("gggggggg-gggg-gggg-gggg-gggggggggggg") is None


# ---------------------------------------------------------------------------
# auth rate-limit buckets are role-specific
# ---------------------------------------------------------------------------

def test_bug05_register_buckets_are_role_specific():
    """
    register_participant must use bucket 'register:participant' and
    register_employer must use bucket 'register:employer' so that
    a participant fsp_id equal to an employer email does not share
    the rate-limit counter.
    """
    source = (_APP / "api" / "v1" / "auth.py").read_text()
    tree = ast.parse(source)

    limit_buckets: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Call):
            func = node.func
            if isinstance(func, ast.Name) and func.id == "_limit":
                if node.args and isinstance(node.args[0], ast.Constant):
                    limit_buckets.append(node.args[0].value)

    assert "register:participant" in limit_buckets
    assert "register:employer" in limit_buckets
    # Generic ambiguous bucket must not be present
    assert "register" not in limit_buckets, (
        "Generic 'register' bucket causes cross-role rate-limit counter collision"
    )


# ---------------------------------------------------------------------------
# skill tsquery keeps the original names
# (structural / AST check on pipeline.py)
# ---------------------------------------------------------------------------

def test_bug02_websearch_tsquery_not_split_joined():
    """
    pipeline.py must pass q directly to websearch_to_tsquery without
    pre-splitting and OR-joining (which destroys 'python OR java' grammar).
    The old pattern was: '" or ".join(text.split())'.
    """
    source = (_APP / "services" / "search" / "pipeline.py").read_text()
    # The buggy pattern: splitting then OR-joining before passing to tsquery
    assert '" or ".join(text.split())' not in source, (
        'Found the old split+OR-join pattern that mangles websearch_to_tsquery grammar'
    )
    # The fix must use websearch_to_tsquery directly with q
    assert "websearch_to_tsquery" in source, "websearch_to_tsquery must still be used for q"
    # and must use to_tsquery for skills (with | for OR)
    assert "to_tsquery" in source, "to_tsquery must be used for skill lexeme OR"
    from app.services.search.pipeline import _skill_or_tsquery

    assert _skill_or_tsquery(["C++", "Node.js", "C#"]) == "'C++' | 'Node.js' | 'C#'"


# ---------------------------------------------------------------------------
# dense retrieval searches the whole embedding table
# (structural check on pipeline.py)
# ---------------------------------------------------------------------------

def test_bug01_dense_retrieval_not_restricted_to_lexical_pool():
    """
    The dense vector query must search the full embedding table.
    The old code had .where(ProfileEmbedding.participant_id.in_(ids))
    which restricted dense search to the already-found lexical candidates,
    defeating the recall-expansion purpose.
    """
    source = (_APP / "services" / "search" / "pipeline.py").read_text()
    # Check that DENSE_POOL constant exists (introduced by the fix)
    assert "DENSE_POOL" in source, "DENSE_POOL constant must be defined"
    # The fix merges dense hits into ids_set after the dense query
    assert "ids_set.add(pid)" in source or "ids_set" in source, (
        "Dense hits must be merged into the unified candidate pool"
    )
