"""Cities and work formats as a search filter. They are not inputs of the match score."""
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
    """Drop only an explicit mismatch. An empty field stays in the list."""
    if city and region and region.casefold() != city.casefold():
        return False
    chosen = [item for item in (formats or []) if item in WORK_FORMATS]
    if work_format and chosen and work_format not in chosen:
        return False
    return True
