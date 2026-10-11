"""Pre-registered expected-gain experiment: the properties fixed before the hold-out run."""
from app.validation import expected_gain as EG
from app.validation import matching as V

NEED = {"role": "backend", "grade": "middle", "skills": ["Python", "PostgreSQL"]}


def _obs(**kw):
    base = {"role": "backend", "grade": "middle", "grade_source": "declared",
            "skills": {"Python": "self_reported", "PostgreSQL": "self_reported"}, "test_p": None, "fsp_lcb": None}
    base.update(kw)
    return base


def test_splits_do_not_overlap():
    seen = set(EG.CALIBRATION_SEEDS) | set(EG.DEV_SEEDS) | set(V.HOLDOUT_SEEDS)
    assert not seen & set(EG.HOLDOUT_SEEDS) and len(EG.HOLDOUT_SEEDS) == 10
    assert EG.LAMBDA in EG.LAMBDA_GRID


def test_beliefs_order_the_trust_levels():
    skills, grades = EG.calibrate()
    assert min(skills["test_confirmed"], skills["resume_confirmed"]) > skills["self_reported"] > skills["missing"]
    for belief in grades.values():
        assert abs(sum(belief.values()) - 1.0) < 1e-9


def test_fsp_never_lowers_the_value_and_absence_is_neutral():
    beliefs = EG.calibrate()
    none = EG.value(NEED, _obs(), beliefs)
    values = [EG.value(NEED, _obs(fsp_lcb=x / 10), beliefs) for x in range(0, 10)]
    assert values == sorted(values) and values[0] >= none


def test_the_ablation_does_not_see_the_test():
    beliefs = EG.calibrate(use_test=False)
    a = EG.value(NEED, _obs(), beliefs, use_test=False, use_fsp=False)
    b = EG.value(NEED, _obs(grade_source="assessed", test_p=0.95), beliefs, use_test=False, use_fsp=False)
    assert a == b
