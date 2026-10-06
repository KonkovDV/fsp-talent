from app.services.categorization import (
    GRADES,
    _ru_word,
    assign_category,
    grade_from_experience,
)

# ---------------------------------------------------------------------------
# Existing tests (unchanged)
# ---------------------------------------------------------------------------

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
    # Contest LCB never becomes an HR grade, including a near-certain top result.
    rookie = assign_category(["Python", "FastAPI"], [{"discipline": "algorithmic", "lcb": 0.95}], experience_years=1)
    assert rookie["grade"] == "junior" and rookie["grade_source"] == "experience"


# ---------------------------------------------------------------------------
# New: grade_from_experience boundary tests
# ---------------------------------------------------------------------------

def test_grade_from_experience_at_exact_boundaries():
    """Границы: <2 → junior, [2, 5) → middle, ≥5 → senior."""
    assert grade_from_experience(None) == "junior"   # нет данных
    assert grade_from_experience(0) == "junior"      # 0 лет
    assert grade_from_experience(1) == "junior"      # 1 год < 2
    assert grade_from_experience(2) == "middle"      # точно на первой границе
    assert grade_from_experience(3) == "middle"
    assert grade_from_experience(4) == "middle"      # последний год до senior
    assert grade_from_experience(5) == "senior"      # точно на второй границе
    assert grade_from_experience(10) == "senior"
    assert grade_from_experience(30) == "senior"


def test_grade_from_experience_returns_valid_grade():
    for years in (None, 0, 1, 2, 5, 20):
        assert grade_from_experience(years) in GRADES


# ---------------------------------------------------------------------------
# New: _ru_word -- Russian morphological agreement
# ---------------------------------------------------------------------------

def test_ru_word_eleven_to_fourteen_always_plural():
    """Числа 11–14 всегда требуют род. падеж множ. числа (множественное)."""
    for n in (11, 12, 13, 14):
        assert _ru_word(n, "год", "года", "лет") == "лет", f"failed for n={n}"
    # Правило распространяется на 111–114, 211–214 и т. д.
    for n in (111, 112, 213, 314):
        assert _ru_word(n, "год", "года", "лет") == "лет", f"failed for n={n}"


def test_ru_word_last_digit_one_singular():
    """Последняя цифра 1 (но не 11) → единственное число."""
    for n in (1, 21, 31, 101, 201):
        assert _ru_word(n, "год", "года", "лет") == "год", f"failed for n={n}"


def test_ru_word_last_digit_two_to_four():
    """Последняя цифра 2–4 (но не 12–14) → род. падеж ед. числа (немногоественное)."""
    for n in (2, 3, 4, 22, 23, 24, 102, 203):
        assert _ru_word(n, "год", "года", "лет") == "года", f"failed for n={n}"


def test_ru_word_last_digit_zero_or_five_to_nine():
    """Последняя цифра 0 или 5–9 → род. падеж мн. числа (множественное)."""
    for n in (0, 5, 6, 7, 8, 9, 10, 15, 20, 25, 100):
        assert _ru_word(n, "год", "года", "лет") == "лет", f"failed for n={n}"


def test_ru_word_negative_input_treated_as_abs():
    """Отрицательные числа: abs() перед применением правил."""
    assert _ru_word(-1, "год", "года", "лет") == "год"
    assert _ru_word(-11, "год", "года", "лет") == "лет"
    assert _ru_word(-3, "год", "года", "лет") == "года"


# ---------------------------------------------------------------------------
# New: stack size cap
# ---------------------------------------------------------------------------

def test_stack_is_capped_at_twelve():
    """assign_category должна возвращать не более 12 навыков в stack."""
    many_skills = [
        "Python", "Go", "FastAPI", "PostgreSQL", "Docker", "Kubernetes",
        "Redis", "Kafka", "Nginx", "Linux", "CI/CD", "Algorithms", "SQL", "MongoDB",
    ]
    result = assign_category(many_skills, [], experience_years=5)
    assert len(result["stack"]) <= 12


# ---------------------------------------------------------------------------
# New: declared_grade validation
# ---------------------------------------------------------------------------

def test_invalid_declared_grade_falls_through_to_experience():
    """Невалидный declared_grade (не в GRADES) не должен перевешивать опыт."""
    result = assign_category(["Python"], [], experience_years=5, declared_grade="wizard")
    assert result["grade_source"] in ("experience", "default")
    assert result["grade"] != "wizard"


# ---------------------------------------------------------------------------
# New: rules_version propagation
# ---------------------------------------------------------------------------

def test_rules_version_is_present():
    from app.services.categorization import RULES_VERSION
    result = assign_category([], [])
    assert result["rules_version"] == RULES_VERSION
    assert result["rules_version"].startswith("v")


def test_survey_specialization_of_a_tester_is_kept():
    result = assign_category(["Python", "PostgreSQL"], [], specialization="qa")
    assert result["primary_role"] == "qa"
    assert any("Тестирование" in line for line in result["explanation"])


def test_survey_specialization_of_a_data_engineer_is_kept():
    result = assign_category(["Python", "SQL"], [], specialization="data")
    assert result["primary_role"] == "data"
    assert any("Инженерия данных" in line for line in result["explanation"])
