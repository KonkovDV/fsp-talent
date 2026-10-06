"""Candidate survey (TZ 2.1): direction and specialization, an optional subject area and what the person seeks.

The TZ word «отрасль» means the IT direction, which is the specialization. INDUSTRIES is the optional
subject area (fintech, retail…), shown in the interface as «Предметная область (необязательно)».
"""
from __future__ import annotations

SPECIALIZATIONS: dict[str, str] = {
    "backend": "Backend-разработка",
    "frontend": "Frontend-разработка",
    "fullstack": "Fullstack-разработка",
    "mobile": "Мобильная разработка",
    "ml": "ML / анализ данных / системы ИИ",
    "devops": "DevOps / инфраструктура",
    "security": "Информационная безопасность",
    "embedded": "Встраиваемые системы, робототехника, БАС",
}
INDUSTRIES: dict[str, str] = {
    "fintech": "Финансы и финтех",
    "ecommerce": "Электронная коммерция и ритейл",
    "gamedev": "Игры",
    "edtech": "Образование",
    "govtech": "Госсектор",
    "telecom": "Телеком",
    "industry": "Промышленность и робототехника",
    "healthtech": "Медицина",
    "media": "Медиа и контент",
    "security": "Кибербезопасность",
    "any": "Не важно",
}
WORK_GOALS: dict[str, str] = {
    "job": "Работа",
    "internship": "Стажировка или практика",
    "both": "Работа или стажировка",
}
