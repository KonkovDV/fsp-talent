"""Phrases that make a vacancy look unsafe. The vacancy stays open. The grade is not involved."""
from __future__ import annotations

_RULES = (
    ("payment", "Просят деньги у кандидата",
     ("оплатите рассмотрение", "взнос за рассмотрение", "переведите на карту", "предоплата от кандидата")),
    ("shadow", "Зарплата мимо оформления",
     ("без оформления", "серая зарплата", "зарплата в конверте")),
    ("appearance", "Отбор по внешности",
     ("славянской внешности", "привлекательная внешность", "только девушек", "только мужчин")),
)


def vacancy_flags(title: str, description: str | None) -> list[dict]:
    text = f"{title or ''}\n{description or ''}".casefold()
    return [
        {"code": code, "label": label}
        for code, label, phrases in _RULES
        if any(phrase in text for phrase in phrases)
    ]
