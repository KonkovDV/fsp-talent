"""Phrases that make a vacancy look unsafe. The vacancy stays open. The grade is not involved."""
from __future__ import annotations

_RULES = (
    ("payment", "Просят деньги у кандидата",
     ("оплатите рассмотрение", "взнос за рассмотрение", "переведите на карту", "предоплата от кандидата")),
    ("shadow", "Зарплата мимо оформления",
     ("без оформления", "серая зарплата", "зарплата в конверте")),
    ("appearance", "Отбор по внешности",
     ("славянской внешности", "привлекательная внешность", "только девушек", "только мужчин")),
    ("pressure", "Давление вместо условий",
     ("молодой дружный коллектив", "дружный коллектив", "мы одна семья", "как семья",
      "стрессоустойчив", "ненормированный рабочий день", "готовность к переработкам",
      "переработк", "работаем на результат, а не на время",
      "зарплата по итогам собеседования", "амбициозный и голодный",
      "быстрый карьерный рост без опыта", "оформление по желанию", "печеньки")),
)


def vacancy_warnings(title: str, description: str | None) -> list[str]:
    """The phrases that fired. The vacancy is still saved."""
    text = f"{title or ''}\n{description or ''}".casefold()
    return [phrase for _, _, phrases in _RULES for phrase in phrases if phrase in text]


def vacancy_flags(title: str, description: str | None) -> list[dict]:
    text = f"{title or ''}\n{description or ''}".casefold()
    return [
        {"code": code, "label": label}
        for code, label, phrases in _RULES
        if any(phrase in text for phrase in phrases)
    ]
