"""Same-scale rows of the assessment validation: report only, no product rule reads them."""
from app.validation.assessment import (
    _matrix_kappa,
    ability_grade,
    parity,
    parity_markdown,
    parity_sessions,
)


def test_matrix_kappa_perfect_and_shifted():
    grades = ["ниже", "intern", "junior", "middle", "senior", "lead"] * 5
    assert _matrix_kappa(grades, grades) == 1.0
    shifted = grades[1:] + grades[:1]
    assert _matrix_kappa(grades, shifted) < 0.5


def test_ability_grade_uses_cuts():
    assert ability_grade(-10.0) == "ниже"
    assert ability_grade(10.0) == "lead"


def test_parity_rows_are_consistent():
    p = parity(parity_sessions(150, 3))
    for x in (p.declared_exact, p.trust_accuracy, p.accuracy, p.overclaim_rejected, p.honest_confirmed):
        assert 0.0 <= x <= 1.0
    low, high = p.kappa_ability_ci
    assert low <= p.kappa_ability <= high or abs(low - high) < 1e-9
    text = parity_markdown(p, 3)
    assert "верить анкете" in text and "только по θ̂" in text


def test_spec_exposure_study_runs_both_denominators():
    from app.validation.assessment import spec_exposure_markdown, spec_exposure_study
    rows = spec_exposure_study(120, 3)
    assert len(rows) == 2 and "своя специализация" in rows[1][0]
    for _, report, kappa, rmse in rows:
        assert 0.0 <= report.spec_max_exposure <= 1.0 and rmse > 0 and -1.0 <= kappa <= 1.0
    assert "RMSE" in spec_exposure_markdown(rows, 3)
