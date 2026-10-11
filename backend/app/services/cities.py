"""Cities and work formats. The search can filter by them, and the match score uses them when named."""
from __future__ import annotations

import re

CITIES = (
    "Москва", "Санкт-Петербург", "Новосибирск", "Екатеринбург", "Казань",
    "Нижний Новгород", "Челябинск", "Самара", "Омск", "Ростов-на-Дону",
    "Уфа", "Красноярск", "Пермь", "Воронеж", "Волгоград",
)
CITY_KEYS = {name.casefold(): name for name in CITIES}
WORK_FORMATS = ("office", "hybrid", "remote")

# Russian case endings of a city noun: «Москва» → «в Москве», «из Москвы», «под Москвой»; «Пермь» → «в Перми».
_ENDINGS = r"(?:а|я|ы|и|е|у|ю|ой|ей|ом|ем|ью|ь)?"
# Everyday names that are not the official one (common in vacancies and on hh.ru).
_ALIASES = {
    "Москва": (r"мск",),
    "Санкт-Петербург": (r"спб", r"питер" + _ENDINGS, r"петербург" + _ENDINGS),
    "Екатеринбург": (r"екб", r"ебург" + _ENDINGS),
    "Нижний Новгород": (r"нижн(?:ий|его|ем|ему|им) новгород" + _ENDINGS, r"н\. ?новгород" + _ENDINGS),
    "Ростов-на-Дону": (r"ростов" + _ENDINGS + r"[ -]на[ -]дону",),
}


def _stem(name: str) -> str:
    """Drop the case ending of the nominative: «Москва» → «Москв», «Пермь» → «Перм», «Омск» stays."""
    return name[:-1] if name[-1] in "аяь" else name


def _city_pattern(name: str) -> re.Pattern[str]:
    if " " in name or "-" in name:
        forms = [re.escape(name.casefold())]
    else:
        forms = [re.escape(_stem(name).casefold()) + _ENDINGS]
    forms += list(_ALIASES.get(name, ()))
    return re.compile(r"(?<!\w)(?:" + "|".join(forms) + r")(?!\w)", re.IGNORECASE)


_CITY_PATTERNS = tuple((name, _city_pattern(name)) for name in CITIES)


def find_city(text: str) -> str | None:
    """The first city the text names, in any case form or common short name («в Казани», «СПб», «Питер»).

    The earliest mention wins: a vacancy names its own office before listing other places.
    """
    hits = [(m.start(), name) for name, pattern in _CITY_PATTERNS if (m := pattern.search(text))]
    return min(hits)[1] if hits else None


def city_name(raw: str | None) -> str | None:
    if not raw:
        return None
    return CITY_KEYS.get(raw.strip().casefold())


def place_keeps(region: str | None, formats: list[str] | None,
                city: str | None, work_format: str | None) -> bool:
    """The list keeps a mismatch. The match score lowers it when the vacancy names a place."""
    del region, formats, city, work_format
    return True
