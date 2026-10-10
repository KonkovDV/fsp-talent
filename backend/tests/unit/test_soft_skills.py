from app.services.soft_skills import clean


def test_only_the_fixed_list_is_stored_and_duplicates_go():
    assert clean(["Лидерство", "Лидерство", "нет такого"]) == ["Лидерство"]
