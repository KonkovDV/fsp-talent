"""Offline checks of the external benchmark mapping and label rule (no download)."""
import math

from app.validation import external_dataset as E

CATALOG = '''
SPEC_SIMILARITY = {("backend", "devops"): 0.35}
SKILLS = [
    ("python", "Python", "language", [], {}, {"go": 0.3}),
    ("postgresql", "PostgreSQL", "db", [], {}, {"mysql": 0.6}),
]
'''
CAND = {"id": 1, "spec": "backend", "theta": 0.9, "true_grade": "middle", "true_skills": {"python": 4, "mysql": 3},
        "declared_skills": {"python": 4, "docker": 2}, "declared_grade": "senior", "verified_grade": "middle",
        "theta_hat": 0.5, "expected_salary": 200000, "work_format": "any"}
JOB = {"id": 0, "spec": "backend", "grade": "middle", "must": ["python", "postgresql"], "nice": ["docker"],
       "salary_to": 270000, "work_format": "remote"}


def test_catalog_is_read_as_literals():
    spec, related = E.parse_catalog(CATALOG)
    assert E.spec_sim(spec, "devops", "backend") == 0.35
    assert E.skill_sim(related, "mysql", "postgresql") == 0.6


def test_label_rule():
    spec, related = E.parse_catalog(CATALOG)
    # coverage (1 + 0.5) / 2 = 0.75, ability 0.85 + 0.3 * 0.9 = 1.12, u = 0.8125 * 1.12 > 0.8
    assert E.label(JOB, CAND, spec, related) == 3
    assert E.label({**JOB, "spec": "frontend"}, CAND, spec, related) == 0


def test_mapping_uses_verified_grade_and_test():
    f = E.to_facts(CAND)
    assert f.grade == "middle" and f.grade_source == "assessed" and f.work_formats == ()
    assert math.isclose(f.test_p, 1 / (1 + math.exp(-1.5)))
    assert set(f.skills.values()) == {"test_confirmed"}
    d = E.to_facts(CAND, declared=True)
    assert d.grade == "senior" and d.test_p is None and set(d.skills.values()) == {"self_reported"}
    assert E.to_need(JOB).work_format == "remote"


def test_metrics_perfect_order():
    assert E.metrics([1, 2, 3], {1: 3, 2: 2, 3: 0}) == (1.0, 0.2, 1.0)
