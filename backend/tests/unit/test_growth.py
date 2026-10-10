"""Growth path: the next grade's common skills, without changing anyone's grade."""
from app.services.growth import growth_gaps, next_grade, skill_reach


def test_the_ladder_stops_at_lead():
    assert next_grade("middle") == "senior"
    assert next_grade("lead") is None
    assert next_grade(None) is None
    assert next_grade("unknown") is None


def test_a_gap_needs_five_people_and_the_role():
    counts = {"PostgreSQL": 12, "React": 10, "Python": 15, "ROS": 2, "Go": 6}
    gaps = growth_gaps("backend", {"Python"}, counts, people=30)
    assert [item["skill"] for item in gaps] == ["PostgreSQL", "Go"]
    assert growth_gaps("backend", {"Python"}, counts, people=4) == []
    assert growth_gaps(None, set(), counts, people=30) == []


def test_one_missing_skill_opens_a_need_and_two_do_not():
    needs = [
        ("backend", ["Python", "PostgreSQL"]),
        ("backend", ["Python", "PostgreSQL"]),
        ("backend", ["Python", "Go"]),
        ("backend", ["Python", "PostgreSQL", "Kafka"]),
        ("security", ["Python", "Linux"]),
    ]
    rows = skill_reach("backend", {"Python"}, needs)
    assert rows == [{"skill": "PostgreSQL", "needs": 2}, {"skill": "Go", "needs": 1}]
    assert skill_reach("backend", {"Python", "PostgreSQL", "Go", "Kafka"}, needs) == []
    assert skill_reach(None, set(), needs) == []
