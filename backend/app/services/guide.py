"""Where to click. The question stays on the server: no profile and no model.

Each answer is a page this role already has. A path outside that list is dropped.
"""
from __future__ import annotations

_CANDIDATE: tuple[dict, ...] = (
    {"keys": ("тест", "грейд"), "title": "Тест на грейд", "to": "/candidate/assessment",
     "text": "Грейд подтверждается в разделе «Тест на грейд». Результат ФСП грейд не ставит."},
    {"keys": ("профиль", "резюме", "согласие"), "title": "Профиль", "to": "/candidate/profile",
     "text": "Имя, контакты и резюме правятся в профиле. Согласия там же."},
    {"keys": ("приглаш", "оффер"), "title": "Приглашения", "to": "/candidate/offers",
     "text": "Ответ компании — в «Приглашениях». Контакты открываются после вашего согласия."},
    {"keys": ("вакан", "отклик"), "title": "Вакансии", "to": "/candidate/vacancies",
     "text": "Открытые вакансии и отклик — в разделе «Вакансии»."},
    {"keys": ("задан", "практик"), "title": "Задания", "to": "/candidate/tasks",
     "text": "Задания компаний и короткая практика — в разделе «Задания». Грейд они не меняют."},
    {"keys": ("фсп", "протокол", "соревн"), "title": "Результаты ФСП", "to": "/candidate/results",
     "text": "Протоколы ФСП — в «Результатах ФСП». Это отдельная ось, не грейд."},
    {"keys": ("обзор", "стаж"), "title": "Обзор", "to": "/candidate",
     "text": "Сводка и путь по грейду — на обзоре."},
)

_EMPLOYER: tuple[dict, ...] = (
    {"keys": ("потребн", "чернов"), "title": "Потребности", "to": "/employer/needs",
     "text": "Кого ищете, описывается в «Потребностях». Текст вакансии можно разобрать там же."},
    {"keys": ("поиск", "карточ", "подбор"), "title": "Поиск", "to": "/employer/search",
     "text": "Банк кандидатов открывается в «Поиске». Имени на карточке нет."},
    {"keys": ("избран", "приоритет"), "title": "Избранное", "to": "/employer/favorites",
     "text": "Отмеченные карточки лежат в «Избранном». Они анонимны."},
    {"keys": ("задан",), "title": "Задания", "to": "/employer/tasks",
     "text": "Свои задания компания даёт в разделе «Задания»."},
    {"keys": ("приглаш", "оффер", "практик"), "title": "Приглашения", "to": "/employer/offers",
     "text": "Отправленные приглашения, практика и собеседование — в «Приглашениях»."},
    {"keys": ("вакан",), "title": "Вакансии", "to": "/employer/vacancies",
     "text": "Публичные вакансии компании — в разделе «Вакансии»."},
    {"keys": ("компан", "довер"), "title": "Компания", "to": "/employer/company",
     "text": "Карточка компании для кандидатов правится в разделе «Компания»."},
    {"keys": ("интегра", "вебхук"), "title": "Интеграции", "to": "/employer/integrations",
     "text": "Вебхуки подключаются в «Интеграциях»."},
)

_PUBLIC: tuple[dict, ...] = (
    {"keys": ("тест", "метод", "вес"), "title": "Как устроен тест", "to": "/method",
     "text": "Параметры теста — на странице «Как устроен тест». Грейд эта страница не ставит."},
    {"keys": ("удостовер", "подпис", "did"), "title": "Проверка удостоверения", "to": "/badge",
     "text": "JSON удостоверения проверяется на странице «Проверка удостоверения». Имени в краткой карточке нет."},
    {"keys": ("жюри", "протокол", "ваканс"), "title": "Режим жюри", "to": "/jury",
     "text": "Демо-входы и публичные страницы собраны в «Режиме жюри»."},
)

_PAGES = {"participant": _CANDIDATE, "employer": _EMPLOYER, "public": _PUBLIC}
_PUBLIC_PATHS = {page["to"] for page in _PUBLIC}


def _allowed(role: str, path: str) -> bool:
    if role == "public":
        return path in _PUBLIC_PATHS
    prefix = "/candidate" if role == "participant" else "/employer"
    return path == prefix or path.startswith(prefix + "/")


def guide(question: str, role: str) -> dict:
    pages = _PAGES.get(role, _CANDIDATE)
    role = role if role in _PAGES else "participant"
    text = question.casefold()
    ranked = []
    for page in pages:
        hits = sum(1 for key in page["keys"] if key in text)
        if hits and _allowed(role, page["to"]):
            ranked.append((hits, page))
    if not ranked:
        links = [{"label": page["title"], "to": page["to"]} for page in pages if _allowed(role, page["to"])]
        return {
            "answer": "Такого раздела не нашлось. Ниже меню вашей роли. Вопрос дальше сервера не уходит.",
            "links": links[:4],
        }
    page = max(ranked, key=lambda item: item[0])[1]
    return {"answer": page["text"], "links": [{"label": page["title"], "to": page["to"]}]}
