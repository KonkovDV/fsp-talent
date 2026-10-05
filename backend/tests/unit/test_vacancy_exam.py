"""A vacancy description changes which topics the grade test serves."""
import random

from app.items.registry import BLUEPRINTS
from app.services import cat
from app.services.vacancy_exam import form_exam


def test_named_skills_pull_the_blueprint_toward_those_topics():
    exam = form_exam(
        "Платежи", "Сервисы на Python и PostgreSQL, немного алгоритмов",
        ["Python", "PostgreSQL"], "backend", "middle",
    )
    shares = {row["topic"]: row["share"] for row in exam["topics"]}
    plain = BLUEPRINTS["backend"]
    assert shares["python"] > plain["python"]
    assert shares["sql"] > plain["sql"]
    assert shares.get("concept", 0) <= 0.30
    assert abs(sum(shares.values()) - 1) < 0.02
    assert exam["samples"]
    assert all("correct" not in sample for sample in exam["samples"])
    assert any(q["skill"] == "PostgreSQL" and "PostgreSQL" in q["evidence"] for q in exam["quotes"])


def test_the_same_vacancy_forms_the_same_samples():
    args = ("Платежи", "Python и PostgreSQL", ["Python"], "backend", "senior")
    assert form_exam(*args)["samples"] == form_exam(*args)["samples"]


def test_a_vacancy_blueprint_does_not_serve_other_topics():
    state = cat.State(spec="backend", target="middle", blueprint={"sql": 0.7, "python": 0.3})
    rng = random.Random(1)
    for _ in range(8):
        choice = cat.choose(state, rng)
        assert choice.family.topic in {"sql", "python"}
        state.families_used[choice.family.id] += 1
        state.topics_used[choice.family.topic] += 1
        state.responses.append(cat.Response(choice.a, choice.b, choice.c, True))
