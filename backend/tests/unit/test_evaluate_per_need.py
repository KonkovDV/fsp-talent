"""public_report: per-need breakdown and the paired model − resume difference on the jury's own pairs."""
import json

from app.validation.matching import parse_pairs, public_report
from app.validation.per_need import paired_delta, per_need

NEED = {"id": "n1", "role": "backend", "grade": "middle", "skills": ["Python", "PostgreSQL"]}
# The pairs behind «Вставить пример» on /evaluate (frontend/src/pages/EvaluatePage.tsx).
PAGE_EXAMPLE = [
    {"need": NEED, "candidate_id": "c1", "candidate": {"observed": {
        "role": "backend", "grade": "middle", "grade_source": "assessed",
        "skills": {"Python": "test_confirmed", "PostgreSQL": "test_confirmed"}, "test_p": 0.9, "fsp_lcb": 0.6,
        "industry": "fintech"}}, "label": 3},
    {"need": NEED, "candidate_id": "c2", "candidate": {"observed": {
        "role": "backend", "grade": "junior", "grade_source": "declared", "skills": {"Python": "self_reported"},
        "test_p": None, "fsp_lcb": None, "industry": "fintech"}}, "label": 1},
    {"need": NEED, "candidate_id": "c3", "candidate": {"observed": {
        "role": "ml", "grade": "senior", "grade_source": "declared", "skills": {"Python": "self_reported"},
        "test_p": None, "fsp_lcb": 0.4, "industry": "fintech"}}, "label": 0},
]


def _text(rows):
    return "\n".join(json.dumps(r, ensure_ascii=False) for r in rows)


def _manual_p(top, k):
    return sum(1 for item in top[:k] if item["label"] >= 2) / k


def test_page_example_has_one_row_per_need_and_p_at_k_matches_the_top():
    report = public_report(_text(PAGE_EXAMPLE))
    assert len(report["per_need"]) == report["needs"] == 1
    row = report["per_need"][0]
    assert row["need_id"] == "n1" and row["judged"] == 3 and row["relevant"] == 1 and row["k"] == 3
    assert row["p_at_k_model"] == round(_manual_p(row["top"], row["k"]), 4)
    assert [item["candidate_id"] for item in row["top"]][0] == "c1"
    assert set(row) >= {"p_at_k_resume", "ndcg10_model", "ndcg10_resume"}


def test_aggregates_are_unchanged_by_the_breakdown():
    report = public_report(_text(PAGE_EXAMPLE))
    full = next(r for r in report["rows"] if r["method"] == "full")
    assert full["ndcg10"] == report["per_need"][0]["ndcg10_model"]
    assert full["p10"] == report["per_need"][0]["p_at_k_model"]


def _two_needs():
    other = {"id": "n2", "role": "frontend", "grade": "junior", "skills": ["React", "TypeScript"]}
    rows = list(PAGE_EXAMPLE)
    rows += [
        {"need": other, "candidate_id": "f1", "candidate": {"observed": {
            "role": "frontend", "grade": "junior", "grade_source": "declared",
            "skills": {"React": "self_reported", "TypeScript": "self_reported"}, "test_p": None, "fsp_lcb": None,
            "industry": "any"}}, "label": 2},
        {"need": other, "candidate_id": "f2", "candidate": {"observed": {
            "role": "frontend", "grade": "junior", "grade_source": "assessed",
            "skills": {"React": "test_confirmed"}, "test_p": 0.8, "fsp_lcb": None, "industry": "any"}}, "label": 3},
        {"need": other, "candidate_id": "f3", "candidate": {"observed": {
            "role": "backend", "grade": "senior", "grade_source": "declared", "skills": {"Python": "self_reported"},
            "test_p": None, "fsp_lcb": None, "industry": "any"}}, "label": 0},
        # A need with no relevant candidate: listed, kept out of the paired mean.
        {"need": {"id": "n3", "role": "qa", "grade": "junior", "skills": ["Selenium"]}, "candidate_id": "q1",
         "candidate": {"observed": {"role": "qa", "grade": "junior", "grade_source": "declared",
                                    "skills": {}, "test_p": None, "fsp_lcb": None, "industry": "any"}}, "label": 1},
    ]
    return rows


def test_every_need_is_listed_and_p_at_k_is_the_share_of_relevant_in_the_top():
    report = public_report(_text(_two_needs()))
    assert [row["need_id"] for row in report["per_need"]] == ["n1", "n2", "n3"]
    assert len(report["per_need"]) == report["needs"]
    for row in report["per_need"]:
        assert row["p_at_k_model"] == round(_manual_p(row["top"], row["k"]), 4)
        assert len(row["top"]) <= 5
    assert report["paired_delta"]["needs"] == 2  # n3 has no relevant candidate


def test_paired_delta_is_the_mean_difference_with_an_interval_around_it():
    report = public_report(_text(_two_needs()))
    rows = report["per_need"]
    deltas = [r["ndcg10_model"] - r["ndcg10_resume"] for r in rows if r["relevant"] > 0]
    delta = report["paired_delta"]
    assert delta["mean"] == round(sum(deltas) / len(deltas), 4)
    low, high = delta["ci"]
    assert low <= delta["mean"] <= high
    assert delta["model_better"] + delta["resume_better"] <= delta["needs"]


def test_two_equal_requests_give_equal_sha_and_paired_delta():
    text = _text(_two_needs())
    first, second = public_report(text), public_report(text)
    assert first["sha256"] == second["sha256"]
    assert first["paired_delta"] == second["paired_delta"]
    assert first["per_need"] == second["per_need"]


def test_no_relevant_need_gives_an_empty_delta():
    data = parse_pairs(_text([PAGE_EXAMPLE[1], PAGE_EXAMPLE[2]]))
    delta = paired_delta(per_need(data))
    assert delta == {"mean": None, "ci": None, "needs": 0, "model_better": 0, "resume_better": 0}
