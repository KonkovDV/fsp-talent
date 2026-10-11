"""A second confirmed specialization is used for that need and does not replace the primary one."""
from types import SimpleNamespace

from app.services.profile_completeness import profile_completeness
from app.services.search.pipeline import _role_for_need, passes_role_grade, shown_category, shown_region


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


def test_a_hidden_city_leaves_the_card_and_stays_in_the_score():
    assert shown_region("Казань", True) == "Казань"
    assert shown_region("Казань", False) is None
    assert shown_region(None, True) is None
    assert shown_region("", False) is None


def _filled(**over):
    base = dict(email_verified=True, birth_date_known=True, survey_done=True, declared_grade="middle",
                assessed_grade="middle", skill_count=2, salary_from=180_000, salary_to=None, region="Казань",
                work_formats=["remote"])
    base.update(over)
    return profile_completeness(**base)


def test_profile_completeness_lists_the_nine_gaps():
    empty = profile_completeness(
        email_verified=False, birth_date_known=False, survey_done=False, declared_grade=None, assessed_grade=None,
        skill_count=0, salary_from=None, salary_to=None, region="  ", work_formats=[])
    assert empty["percent"] == 0 and empty["done"] == 0 and empty["total"] == 9
    assert empty["missing"] == ["email", "birth_date", "survey", "grade", "test", "skills", "salary", "city", "format"]
    one = _filled(email_verified=False, birth_date_known=False, survey_done=False, declared_grade=None,
                  assessed_grade=None, skill_count=0, salary_from=None, salary_to=100_000, region=None,
                  work_formats=None)
    assert one["missing"] == ["email", "birth_date", "survey", "grade", "test", "skills", "city", "format"]
    assert one["percent"] == 11
    confirmed = _filled(declared_grade=None)
    assert confirmed["missing"] == [] and confirmed["percent"] == 100
    assert _filled()["items"][0]["href"] is None


def test_a_second_grade_is_not_hidden_by_the_primary_grade():
    confirmed = [("security", "junior")]
    assert passes_role_grade("backend", "middle", confirmed, "security", "junior") is True
    assert passes_role_grade("backend", "middle", confirmed, "security", "senior") is False
    assert passes_role_grade("backend", "middle", confirmed, None, "junior") is False


def test_a_profile_without_a_birth_date_never_reads_100_percent():
    # SD-01 / SDK-02: without the date the card is hidden from search, so the checklist asks for it.
    no_date = _filled(declared_grade=None, birth_date_known=False)
    assert no_date["missing"] == ["birth_date"] and no_date["percent"] == 89
    item = next(i for i in no_date["items"] if i["code"] == "birth_date")
    assert item["href"] == "/candidate/profile" and "поиске" in item["label"]
