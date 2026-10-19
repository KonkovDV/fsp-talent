"""A practical case and a follow-up, chosen by industry. One rubric for every plot.

Both answers are integers the plot determines. The grade does not move.
"""
from __future__ import annotations

from app.services.survey import INDUSTRIES

RUBRIC_BOTH = "оба ответа сошлись с рубрикой"
RUBRIC_CASE = "сошёлся кейс, уточняющий вопрос нет"
RUBRIC_FOLLOW = "сошёлся уточняющий вопрос, кейс нет"
RUBRIC_NONE = "рубрика не сошлась"


def _rubric(first_ok: bool, follow_ok: bool) -> str:
    if first_ok and follow_ok:
        return RUBRIC_BOTH
    if first_ok:
        return RUBRIC_CASE
    if follow_ok:
        return RUBRIC_FOLLOW
    return RUBRIC_NONE


def _number(text: str) -> int | None:
    raw = (text or "").strip().replace(" ", "")
    if raw.startswith("+"):
        raw = raw[1:]
    if not raw.isdigit():
        return None
    return int(raw)


# (title, plot, ask, follow question, first answer, follow answer)
_PLOTS: dict[str, tuple[str, str, str, str, int, int]] = {
    "fintech": (
        "Комиссия перевода",
        "Комиссия 1 % суммы, но не меньше 30.",
        "Какая комиссия с 10 000?",
        "Сумма стала 2 000. Какая теперь комиссия?",
        max(30, 10_000 // 100),
        max(30, 2_000 // 100),
    ),
    "ecommerce": (
        "Корзина",
        "Товар стоит 400. Скидка 10 % начинается от суммы 1 000.",
        "Сколько к оплате за 3 товара?",
        "Товар убрали, осталось 2. Сколько к оплате?",
        3 * 400 - 3 * 400 // 10,
        2 * 400,
    ),
    "gamedev": (
        "Урон",
        "Удар 40. Броня снимает четверть урона, округление вниз.",
        "Какой урон пройдёт?",
        "Броню сняли. Какой урон пройдёт?",
        40 - 40 // 4,
        40,
    ),
    "edtech": (
        "Занятие",
        "Урок 45 минут. Между уроками перерыв 10 минут.",
        "Сколько минут займут 4 урока?",
        "Уроков стало 3. Сколько минут это займёт?",
        4 * 45 + 3 * 10,
        3 * 45 + 2 * 10,
    ),
    "govtech": (
        "Срок",
        "На заявку дано 10 рабочих дней.",
        "Сколько дней осталось, если прошло 4?",
        "Прошло 7 дней. Сколько осталось?",
        10 - 4,
        10 - 7,
    ),
    "telecom": (
        "Трафик",
        "В пакете 200 МБ. Дальше 2 за каждый мегабайт.",
        "Сколько доплатить за 500 МБ?",
        "Потрачено 150 МБ. Сколько доплатить?",
        (500 - 200) * 2,
        0,
    ),
    "industry": (
        "Смена",
        "Норма 8 часов по 500. Сверхурочные считаются как полтора часа.",
        "Сколько начислить за 10 часов?",
        "Смена стала 8 часов. Сколько начислить?",
        8 * 500 + 2 * 500 + 2 * 250,
        8 * 500,
    ),
    "healthtech": (
        "Назначение",
        "По 2 приёма в день.",
        "Сколько приёмов за 7 дней?",
        "Курс стал 10 дней. Сколько приёмов?",
        2 * 7,
        2 * 10,
    ),
    "media": (
        "Досмотр",
        "Ролик посмотрели 1 000 раз. До конца доходит 40 %.",
        "Сколько полных просмотров?",
        "До конца доходит 25 %. Сколько полных просмотров?",
        1_000 * 40 // 100,
        1_000 * 25 // 100,
    ),
    "security": (
        "Пароль",
        "Пароль меняют каждые 90 дней. В году 360 дней.",
        "Сколько смен за год?",
        "Срок стал 180 дней. Сколько смен за год?",
        360 // 90,
        360 // 180,
    ),
    "any": (
        "Очередь",
        "Разбор идёт по 5 заявок в час.",
        "Сколько заявок за 6 часов?",
        "Смена стала 4 часа. Сколько заявок?",
        5 * 6,
        5 * 4,
    ),
}


def _plot(industry: str) -> tuple[str, tuple]:
    code = industry if industry in _PLOTS else "any"
    return code, _PLOTS[code]


def present(industry: str | None) -> dict:
    code, row = _plot(industry or "any")
    title, plot, ask, follow, _first, _second = row
    return {
        "industry": code,
        "label": INDUSTRIES.get(code, INDUSTRIES["any"]),
        "title": title,
        "plot": plot,
        "ask": ask,
        "follow": follow,
        "grade_unchanged": True,
    }


def judge(industry: str | None, first: str, follow: str) -> dict:
    code, row = _plot(industry or "any")
    _title, _plot_text, _ask, _follow_ask, expected_first, expected_follow = row
    first_ok = _number(first) == expected_first
    follow_ok = _number(follow) == expected_follow
    return {
        "industry": code,
        "rubric": _rubric(first_ok, follow_ok),
        "first_ok": first_ok,
        "follow_ok": follow_ok,
        "grade_unchanged": True,
    }
