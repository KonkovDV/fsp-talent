from app.services.need_draft import draft_need
from app.services.vacancy_flags import vacancy_flags, vacancy_warnings


def test_money_and_appearance_are_named_and_a_plain_vacancy_is_quiet():
    flags = vacancy_flags("Стажёр", "Оплатите рассмотрение и ищем только девушек")
    assert [item["code"] for item in flags] == ["payment", "appearance"]
    assert vacancy_flags("Бэкенд", "Python и PostgreSQL, удалённо") == []
    pressure = vacancy_flags("Бэкенд", "Молодой дружный коллектив и готовность к переработкам")
    assert [item["code"] for item in pressure] == ["pressure"]
    warnings = vacancy_warnings(
        "Бэкенд", "Амбициозный и голодный, печеньки, оформление по желанию, стрессоустойчивость")
    assert "амбициозный и голодный" in warnings
    assert "печеньки" in warnings
    assert "оформление по желанию" in warnings
    assert "стрессоустойчив" in warnings
    draft = draft_need("Ищем стажёра на Python. Оплатите рассмотрение. Вилка 80000-120000, удалённо, Москва.")
    assert any(item["code"] == "payment" for item in draft["flags"])
