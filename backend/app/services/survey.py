"""Candidate survey (TZ 2.1): specialization, industry and what the person is looking for."""
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
