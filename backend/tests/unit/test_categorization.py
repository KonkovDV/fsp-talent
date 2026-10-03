from app.services.categorization import assign_category


def test_skills_outrank_discipline_and_declaration_outranks_experience():
    by_skills = assign_category(["Python", "FastAPI"], [{"discipline": "security", "lcb": 0.9}])
    assert by_skills["primary_role"] == "backend"
    by_discipline = assign_category([], [{"discipline": "security", "lcb": 0.5}, {"discipline": "bas", "lcb": 0.1}])
    assert by_discipline["primary_role"] == "security"
    declared = assign_category(["Python", "Go"], [], experience_years=6, declared_grade="junior")
    assert declared["grade"] == "junior" and declared["grade_source"] == "declared"
    experienced = assign_category(["Python", "Go"], [], experience_years=6)
    assert experienced["grade"] == "senior" and experienced["grade_source"] == "experience"
    years = assign_category(["Python", "Go"], [], experience_years=3)
    assert any("3 года" in line for line in years["explanation"])
    many = assign_category(["Python", "Go", "FastAPI", "PostgreSQL", "Docker", "Algorithms"], [], experience_years=5)
    assert any("6 подтверждённых навыков" in line for line in many["explanation"])
    assert any("5 лет" in line for line in many["explanation"])
    unknown = assign_category([], [])
    assert unknown["primary_role"] == "fullstack"
    assert unknown["grade_source"] == "default"
