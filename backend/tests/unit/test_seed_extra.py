"""Synthetic load profiles are not people and do not depend on the database."""
from app.api.v1.needs import cached_page
from seed.generate_seed import extra_email, extra_spec, showcase_adds


def test_extra_profile_has_no_personal_data_and_is_stable():
    one = extra_spec(1)
    assert one == extra_spec(1)
    assert one["email"] == extra_email(1) == "extra00001@load.talent"
    assert one["display_name"].startswith("Профиль ")
    assert "phone" not in one and "telegram" not in one and "birth_date" not in one
    assert one["specialization"] in {"backend", "frontend", "fullstack", "ml", "devops", "qa"}
    assert one["declared_grade"] in {"intern", "junior", "middle", "senior", "lead"}
    assert 3 <= len(one["skills"]) <= 4


def test_cached_shortlist_returns_a_stored_page_only():
    stored = {"pages": {"40:20": [{"n": 1}]}, "total": 1000}
    page = cached_page(stored, 40, 20)
    assert page is not None and page["items"] == [{"n": 1}] and page["total"] == 1000
    assert "pages" not in page
    assert cached_page(stored, 0, 20) is None


def test_showcase_fills_six_rows_and_one_edge_cell():
    counts = {("backend", "junior"): 31, ("backend", "middle"): 13, ("backend", "senior"): 30, ("backend", "intern"): 1}
    adds = {(spec, grade): n for spec, grade, n in showcase_adds(counts)}
    assert ("backend", "junior") not in adds
    assert adds[("backend", "intern")] == 4
    assert adds[("frontend", "junior")] == 6
    assert adds[("qa", "senior")] == 6
    assert all(n > 0 for _, _, n in showcase_adds(counts))
