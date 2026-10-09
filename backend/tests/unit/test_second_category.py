"""A second confirmed specialization is used for that need and does not replace the primary one."""
from types import SimpleNamespace

from app.services.search.pipeline import _role_for_need


def test_the_need_role_uses_its_own_confirmation():
    cat = SimpleNamespace(primary_role="backend", grade="middle", grade_source="assessed")
    other = SimpleNamespace(specialization="security", grade="junior")
    assert _role_for_need(cat, "security", other) == ("security", "junior", "assessed")
    assert _role_for_need(cat, "backend", other) == ("backend", "middle", "assessed")
    assert _role_for_need(cat, None, other) == ("backend", "middle", "assessed")
