"""Regression checks for models, credentials and registration (no DB, no Redis, no network).

- ProfileSearchIndex.updated_at is refreshed on update
- one Result per (participant, event)
- the issuer public key is computed once
- a credential with validFrom in the future is rejected
- a registration race returns 409, not 500
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).parent.parent.parent  # backend/


def _src(relpath: str) -> str:
    return (ROOT / relpath).read_text()


class TestProfileSearchIndexUpdatedAt:
    def test_psi_updated_at_has_onupdate(self):
        src = _src("app/models/profile.py")
        tree = ast.parse(src)
        psi_body = next(
            n for n in ast.walk(tree)
            if isinstance(n, ast.ClassDef) and n.name == "ProfileSearchIndex"
        )
        for stmt in ast.walk(psi_body):
            if isinstance(stmt, ast.Assign):
                for t in stmt.targets:
                    if isinstance(t, ast.Name) and t.id == "updated_at":
                        kw_names = {kw.arg for kw in stmt.value.keywords}
                        assert "onupdate" in kw_names, (
                            "ProfileSearchIndex.updated_at missing onupdate=. "
                            "rebuild_profile UPDATE leaves timestamp frozen."
                        )
                        assert "default" in kw_names, "updated_at missing default="
                        return
        pytest.fail("updated_at not found in ProfileSearchIndex")

    def test_psi_file_parses(self):
        ast.parse(_src("app/models/profile.py"))


class TestResultUniqueConstraint:
    def test_result_has_uq_participant_event(self):
        src = _src("app/models/participant.py")
        assert "uq_result_participant_event" in src, (
            "Result missing UniqueConstraint(participant_id, event_id). "
            "Duplicate ingest inflates n_eff, rankings gameable."
        )

    def test_participant_file_parses(self):
        ast.parse(_src("app/models/participant.py"))


class TestPublicKeyMultibaseCached:
    def test_public_key_multibase_has_lru_cache(self):
        src = _src("app/services/vc/issuer.py")
        tree = ast.parse(src)
        fn = next(
            (n for n in ast.walk(tree)
             if isinstance(n, ast.FunctionDef) and n.name == "public_key_multibase"),
            None,
        )
        assert fn is not None, "public_key_multibase not found"
        deco_names = []
        for d in fn.decorator_list:
            if isinstance(d, ast.Name):
                deco_names.append(d.id)
            elif isinstance(d, ast.Call):
                func = d.func
                deco_names.append(func.id if isinstance(func, ast.Name) else getattr(func, "attr", ""))
        assert "lru_cache" in deco_names, "public_key_multibase must be @lru_cache"

    def test_issuer_file_parses(self):
        ast.parse(_src("app/services/vc/issuer.py"))


class TestVerifyCredentialValidFrom:
    def test_verify_credential_checks_valid_from(self):
        src = _src("app/services/vc/issuer.py")
        tree = ast.parse(src)
        vc_fn = next(
            (n for n in ast.walk(tree)
             if isinstance(n, ast.FunctionDef) and n.name == "verify_credential"),
            None,
        )
        assert vc_fn is not None
        fn_src = ast.get_source_segment(src, vc_fn) or ""
        assert "validFrom" in fn_src, "verify_credential must inspect validFrom"
        assert "datetime.now" in fn_src or "timezone.utc" in fn_src, (
            "verify_credential must compare validFrom to current time"
        )


class TestRegisterTOCTOU:
    def _auth_fn(self, name: str) -> tuple[str, ast.AsyncFunctionDef]:
        src = _src("app/api/v1/auth.py")
        tree = ast.parse(src)
        fn = next(
            (n for n in ast.walk(tree)
             if isinstance(n, ast.AsyncFunctionDef) and n.name == name),
            None,
        )
        assert fn is not None, f"{name} not found"
        return src, fn

    def test_register_participant_catches_integrity_error(self):
        src, fn = self._auth_fn("register_participant")
        fn_src = ast.get_source_segment(src, fn) or ""
        assert "IntegrityError" in fn_src, (
            "register_participant must catch IntegrityError (TOCTOU on fsp_id UNIQUE)"
        )
        assert "rollback" in fn_src, "must rollback before raising 409"

    def test_register_employer_catches_integrity_error(self):
        src, fn = self._auth_fn("register_employer")
        fn_src = ast.get_source_segment(src, fn) or ""
        assert "IntegrityError" in fn_src, (
            "register_employer must catch IntegrityError (TOCTOU on email UNIQUE)"
        )

    def test_auth_file_parses(self):
        ast.parse(_src("app/api/v1/auth.py"))
