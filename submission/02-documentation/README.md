# Документация

[FSP_Talent_documentation.pdf](FSP_Talent_documentation.pdf) — основные документы одним PDF. Это копия [docs/FSP_Talent_documentation.pdf](https://github.com/KonkovDV/fsp-talent/blob/main/docs/FSP_Talent_documentation.pdf), собирается командой `make docs-pdf`.

С чего начать:

- [SOLUTION.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/SOLUTION.md) — сопроводительная документация по восьми пунктам раздела 3.4 ТЗ: архитектура, механики, валидация, интеграция, API, библиотеки.
- [INSTALL.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/INSTALL.md) — локальный запуск, развёртывание на сервере, обновление, откат, резервные копии, частые проблемы.
- [USER_GUIDE.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/USER_GUIDE.md) — руководство пользователя: кандидат, работодатель, проверяющий, законный представитель.

Остальные документы в `docs/`:

| Документ | О чём |
|---|---|
| [REQUIREMENTS.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/REQUIREMENTS.md) | Каждое исходное требование и уточнения к нему: где увидеть и где в коде |
| [BEYOND_TZ.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/BEYOND_TZ.md) | Что сделано сверх ТЗ: психометрика, удостоверения W3C VC, безопасность, доступность, валидация |
| [REQUIREMENTS_QA.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/REQUIREMENTS_QA.md) | Уточнения требований, у каждого — тест или файл, который это подтверждает |
| [REVIEW_GUIDE.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/REVIEW_GUIDE.md) | Как проверить каждое ключевое свойство: где нажать, какую команду запустить, что увидеть |
| [MODEL_CARDS.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/MODEL_CARDS.md) | Карточки моделей теста и подбора: назначение, данные, ограничения |
| [DATASETS.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/DATASETS.md) | Синтетические данные: как построены и чем не являются |
| [ACCESSIBILITY.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/ACCESSIBILITY.md) | Доступность: WCAG 2.2 AA, замеры axe и Lighthouse |
| [VALIDATION_ASSESSMENT.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/VALIDATION_ASSESSMENT.md) | Проверка теста на грейд: ключи заданий запуском (1875/1875), повтор процедуры, сопоставимые строки, кривые сигналов честности, EAP против WLE |
| [VALIDATION_MATCHING.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/VALIDATION_MATCHING.md) | Проверка подбора кандидатов: лестница баз, градуированные протоколы с P@10 и MRR |
| [VALIDATION_INTEGRITY.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/VALIDATION_INTEGRITY.md) | Уровень риска честности теста |
| [VALIDATION_NLP.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/VALIDATION_NLP.md) | Разбор резюме и вакансий по полям |
| [PREREG_MATCHING_2026-10.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/PREREG_MATCHING_2026-10.md) | Предрегистрация гипотез по ранжированию до запуска на отложенных данных |
| [LOAD_TEST.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/LOAD_TEST.md) | Нагрузочная проверка |
| [FSP_INTEGRATION.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/FSP_INTEGRATION.md) | ФСП ID (OIDC, Keycloak) и контракт реестра ФСП |
| [TRUST_AND_ATS.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/TRUST_AND_ATS.md) | Защита от фиктивных вакансий и интеграция с ATS |
| [COMPLIANCE.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/COMPLIANCE.md) | Персональные данные (152-ФЗ), честность решений, права |
| Юридические тексты | Действующие версии: [согласие кандидата 1.4](https://github.com/KonkovDV/fsp-talent/blob/main/backend/app/legal/docs/pd_candidate.md), [согласие на распространение 1.1](https://github.com/KonkovDV/fsp-talent/blob/main/backend/app/legal/docs/pd_distribution.md), [согласие работодателя 1.3](https://github.com/KonkovDV/fsp-talent/blob/main/backend/app/legal/docs/pd_employer.md), [политика 1.2](https://github.com/KonkovDV/fsp-talent/blob/main/backend/app/legal/docs/privacy_policy.md), [пользовательское соглашение 1.1](https://github.com/KonkovDV/fsp-talent/blob/main/backend/app/legal/docs/terms.md), [правила рекомендательных технологий 1.1](https://github.com/KonkovDV/fsp-talent/blob/main/backend/app/legal/docs/recommendations.md) |
| [API_ERRORS.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/API_ERRORS.md) | Коды ошибок API |
| [BUSINESS.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/BUSINESS.md) | Бизнес-модель: кто платит и за что, каналы найма и их ограничения |
| [DESIGN.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/DESIGN.md) | Дизайн-система «Протокол» по брендбуку ФСП |
| [THIRD_PARTY.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/THIRD_PARTY.md) | Сторонние компоненты и лицензии |
| [requirements_trace.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/requirements_trace.md) | Прослеживаемость: требование → проверка, `make accept` |
| [ARCHITECTURE.md](https://github.com/KonkovDV/fsp-talent/blob/main/ARCHITECTURE.md) | Главные архитектурные решения коротко |

## Что мы измерили и где границы

- Все числа в документации получены запуском кода, команда стоит рядом с каждым числом. Расхождение чисел в README и `docs/` со свежим прогоном ловит `python tests/doc_numbers.py` в `backend/`.
- Качество теста и подбора измерено на синтетике со скрытой правдой. На живых кандидатах ФСП мы его ещё не мерили, живого эталона найма ещё нет. Дизайн пилота описан в README.
