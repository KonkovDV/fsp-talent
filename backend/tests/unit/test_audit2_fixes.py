"""
Checks for offer reveal, vacancy listing and the profile rebuild lock.

All tests are static-analysis only (no DB, no Redis, no imports of app code).
They run in the CI unit job without any infrastructure.
"""
from __future__ import annotations

import ast
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).parent.parent.parent  # backend/
APP = ROOT / "app"


def _read(rel: str) -> str:
    return (ROOT / rel).read_text()


# ---------------------------------------------------------------------------
# BUG-A: contacts_revealed_at must be stamped in reveal_contacts
# ---------------------------------------------------------------------------
class TestBugA_ContactsRevealedAt(unittest.TestCase):
    def setUp(self):
        self.src = _read("app/api/v1/offers.py")

    def test_field_is_assigned(self):
        """offer.contacts_revealed_at = ... must exist."""
        self.assertRegex(
            self.src,
            r"offer\.contacts_revealed_at\s*=",
            "BUG-A: reveal_contacts must stamp offer.contacts_revealed_at",
        )

    def test_idempotent_guard(self):
        """Must be guarded with 'if offer.contacts_revealed_at is None'."""
        self.assertIn(
            "contacts_revealed_at is None",
            self.src,
            "BUG-A: stamp must be idempotent (if offer.contacts_revealed_at is None:)",
        )

    def test_exposed_in_response(self):
        """contacts_revealed_at must appear as a response key."""
        self.assertIn(
            '"contacts_revealed_at"',
            self.src,
            "BUG-A: contacts_revealed_at must be returned in the API response",
        )


# ---------------------------------------------------------------------------
# BUG-B: vacancies_for_me must have a LIMIT
# ---------------------------------------------------------------------------
class TestBugB_VacanciesLimit(unittest.TestCase):
    def setUp(self):
        self.src = _read("app/api/v1/vacancies.py")

    def test_limit_constant_or_call_exists(self):
        has_const = "_VACANCY_SCAN_LIMIT" in self.src
        has_call = re.search(r"\.limit\s*\(", self.src) is not None
        self.assertTrue(
            has_const or has_call,
            "BUG-B: vacancies_for_me must use .limit() or _VACANCY_SCAN_LIMIT",
        )

    def test_limit_value_is_sane(self):
        m = re.search(r"_VACANCY_SCAN_LIMIT\s*=\s*(\d+)", self.src)
        if m is None:
            m = re.search(r"\.limit\s*\((\d+)\)", self.src)
        if m is None:
            self.skipTest("Limit not a literal; manual review required")
        val = int(m.group(1))
        self.assertGreater(val, 0)
        self.assertLessEqual(val, 5000, "LIMIT must be <= 5000")


# ---------------------------------------------------------------------------
# BUG-C: Vacancy model must have updated_at
# ---------------------------------------------------------------------------
class TestBugC_VacancyUpdatedAt(unittest.TestCase):
    def setUp(self):
        self.src = _read("app/models/vacancy.py")

    def test_column_exists(self):
        self.assertIn("updated_at", self.src, "BUG-C: Vacancy must have updated_at column")

    def test_has_default(self):
        idx = self.src.find("updated_at")
        snippet = self.src[idx: idx + 300]
        self.assertIn("default", snippet, "BUG-C: updated_at must have default= for INSERT")

    def test_has_onupdate(self):
        idx = self.src.find("updated_at")
        snippet = self.src[idx: idx + 300]
        self.assertIn("onupdate", snippet, "BUG-C: updated_at must have onupdate= for UPDATE")


# ---------------------------------------------------------------------------
# BUG-D: tasks.py must have an idempotency / concurrency guard
# ---------------------------------------------------------------------------
class TestBugD_RebuildLock(unittest.TestCase):
    def setUp(self):
        self.src = _read("app/workers/tasks.py")

    def test_lock_acquired(self):
        self.assertTrue(
            "_acquire_rebuild_lock" in self.src or "rebuild_lock" in self.src,
            "BUG-D: _rebuild must acquire a distributed lock",
        )

    def test_lock_key_scoped_per_participant(self):
        has_scoped = (
            re.search(r'["\']rebuild_lock:["\']', self.src) is not None
            or "_REBUILD_LOCK_PREFIX" in self.src
        )
        self.assertTrue(has_scoped, "BUG-D: lock key must be scoped per participant_id")

    def test_lock_has_ttl(self):
        has_ttl = (
            "_REBUILD_LOCK_TTL" in self.src
            or re.search(r"ex\s*=", self.src) is not None
        )
        self.assertTrue(has_ttl, "BUG-D: lock must have a TTL")

    def test_lock_released_in_finally(self):
        self.assertIn("finally", self.src, "BUG-D: must use try/finally to release lock")
        self.assertTrue(
            "_release_rebuild_lock" in self.src or "delete" in self.src,
            "BUG-D: lock must be released in finally block",
        )


# ---------------------------------------------------------------------------
# Syntax sanity
# ---------------------------------------------------------------------------
class TestSyntax(unittest.TestCase):
    def _check(self, rel: str):
        src = _read(rel)
        try:
            ast.parse(src)
        except SyntaxError as e:
            self.fail(f"{rel} has SyntaxError: {e}")

    def test_offers(self):          self._check("app/api/v1/offers.py")
    def test_vacancies(self):       self._check("app/api/v1/vacancies.py")
    def test_vacancy_model(self):   self._check("app/models/vacancy.py")
    def test_tasks(self):           self._check("app/workers/tasks.py")


if __name__ == "__main__":
    unittest.main()
