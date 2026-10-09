"""Cities and work formats. The search can filter by them, and the match score uses them when named."""
from __future__ import annotations

CITIES = (
    "Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург", "Казань",
    "Нижний Новгород", "Челябинск", "Самара", "Омск", "Ростов-на-Дону",
    "Уфа", "Красноярск", "Пермь", "Воронеж", "Волгоград",
)
CITY_KEYS = {name.casefold(): name for name in CITIES}
WORK_FORMATS = ("office", "hybrid", "remote")


def city_name(raw: str | None) -> str | None:
    if not raw:
        return None
    return CITY_KEYS.get(raw.strip().casefold())


def place_keeps(region: str | None, formats: list[str] | None,
                city: str | None, work_format: str | None) -> bool:
    """The list keeps a mismatch. The match score lowers it when the vacancy names a place."""
    del region, formats, city, work_format
    return True
