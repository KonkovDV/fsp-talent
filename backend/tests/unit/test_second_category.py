"""A second confirmed specialization is used for that need and does not replace the primary one."""
from types import SimpleNamespace

from app.services.search.pipeline import _role_for_need, passes_role_grade, shown_category


def test_the_need_role_uses_its_own_confirmation():
    cat = SimpleNamespace(primary_role="backend", grade="middle", grade_source="assessed")
    other = SimpleNamespace(specialization="security", grade="junior")
    assert _role_for_need(cat, "security", other) == ("security", "junior", "assessed")
    assert _role_for_need(cat, "backend", other) == ("backend", "middle", "assessed")
    assert _role_for_need(cat, None, other) == ("backend", "middle", "assessed")
    role, grade, source, also = shown_category("backend", "middle", "assessed", "security", "junior", "assessed")
    assert (role, grade, source) == ("security", "junior", "assessed")
    assert also == {"role": "backend", "grade": "middle", "grade_source": "assessed"}
    assert shown_category("backend", "middle", "assessed", "backend", "middle", "assessed") == (
        "backend", "middle", "assessed", None)


def test_a_second_grade_is_not_hidden_by_the_primary_grade():
    confirmed = [("security", "junior")]
    assert passes_role_grade("backend", "middle", confirmed, "security", "junior") is True
    assert passes_role_grade("backend", "middle", confirmed, "security", "senior") is False
    assert passes_role_grade("backend", "middle", confirmed, None, "junior") is False
