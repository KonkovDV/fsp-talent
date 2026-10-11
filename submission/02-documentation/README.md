# Документация

**Файл для формы:** [FSP_Talent_documentation.pdf](FSP_Talent_documentation.pdf) — вся документация одним PDF. Это копия [docs/FSP_Talent_documentation.pdf](https://github.com/KonkovDV/fsp-talent/blob/main/docs/FSP_Talent_documentation.pdf), собирается командой `make docs-pdf`.

С чего начать:

- [SOLUTION.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/SOLUTION.md) — сопроводительная документация по восьми пунктам раздела 3.4 ТЗ: архитектура, механики, валидация, интеграция, API, библиотеки.
- [INSTALL.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/INSTALL.md) — локальный запуск, развёртывание на сервере, обновление, откат, резервные копии, частые проблемы.
- [USER_GUIDE.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/USER_GUIDE.md) — руководство пользователя стенда: кандидат, работодатель, жюри, законный представитель.

Остальные документы в `docs/`:

| Документ | О чём |
|---|---|
| [REQUIREMENTS.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/REQUIREMENTS.md) | Каждое требование ТЗ и ответы постановщика на Q&A: где увидеть и где в коде |
| [BEYOND_TZ.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/BEYOND_TZ.md) | Что сделано сверх ТЗ: психометрика, удостоверения W3C VC, безопасность, доступность, валидация |
| [VALIDATION_ASSESSMENT.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/VALIDATION_ASSESSMENT.md) | Проверка теста на грейд |
| [VALIDATION_MATCHING.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/VALIDATION_MATCHING.md) | Проверка подбора кандидатов |
| [VALIDATION_INTEGRITY.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/VALIDATION_INTEGRITY.md) | Уровень риска честности теста |
| [VALIDATION_NLP.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/VALIDATION_NLP.md) | Разбор резюме и вакансий по полям |
| [PREREG_MATCHING_2026-10.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/PREREG_MATCHING_2026-10.md) | Предрегистрация гипотез по ранжированию до запуска на отложенных данных |
| [LOAD_TEST.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/LOAD_TEST.md) | Нагрузочная проверка |
| [FSP_INTEGRATION.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/FSP_INTEGRATION.md) | ФСП ID (OIDC, Keycloak) и контракт реестра ФСП |
| [TRUST_AND_ATS.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/TRUST_AND_ATS.md) | Защита от фиктивных вакансий и интеграция с ATS |
| [COMPLIANCE.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/COMPLIANCE.md) | Персональные данные (152-ФЗ), честность решений, права |
| [API_ERRORS.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/API_ERRORS.md) | Коды ошибок API |
| [DESIGN.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/DESIGN.md) | Дизайн-система «Протокол» по брендбуку ФСП |
| [THIRD_PARTY.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/THIRD_PARTY.md) | Сторонние компоненты и лицензии |
| [requirements_trace.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/requirements_trace.md) | Прослеживаемость: требование → проверка, `make accept` |
| [ARCHITECTURE.md](https://github.com/KonkovDV/fsp-talent/blob/main/ARCHITECTURE.md) | Ключевые архитектурные решения коротко |

## Что измерено и чем это не является

- Все числа в документации получены запуском кода, команда стоит рядом с каждым числом. Расхождение чисел в README и `docs/` со свежим прогоном ловит `python tests/doc_numbers.py` в `backend/`.
- Качество теста и подбора измерено на синтетике со скрытой правдой. Это не замер на живых кандидатах ФСП: такого эталона в хакатоне нет, дизайн пилота описан в README.
