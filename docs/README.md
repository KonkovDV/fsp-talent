# Документация ФСП Талант

Документы разложены по задаче читателя: научиться, сделать, свериться или понять, почему так. Каждое число в документах печатается командой с фиксированным зерном, а CI сверяет опубликованные цифры со свежим прогоном (`backend/tests/doc_numbers.py`).

## Начать

| Документ | Для чего |
|---|---|
| [README: быстрый старт](../README.md#быстрый-старт) | Поднять стенд одной командой и войти демо-аккаунтом |
| [INSTALL.md](INSTALL.md) | Требования, запуск, проверка, демо-входы и частые проблемы |
| [USER_GUIDE.md](USER_GUIDE.md) | Путь кандидата, работодателя, проверяющего и законного представителя; полный сценарий на 15 шагов |

## Сделать

| Документ | Для чего |
|---|---|
| [REVIEW_GUIDE.md](REVIEW_GUIDE.md) | Проверить каждое ключевое свойство: где нажать, какую команду запустить, что увидеть |
| [INSTALL.md, раздел 11](INSTALL.md#11-развёртывание-на-сервере) и [deploy/README.md](../deploy/README.md) | Развернуть на сервере с HTTPS, обновить, откатить, восстановить из копии |
| [FSP_INTEGRATION.md](FSP_INTEGRATION.md) | Подключить настоящий ФСП ID (Keycloak) и реестр протоколов |
| [LOAD_TEST.md](LOAD_TEST.md) | Повторить нагрузочную проверку |
| [CONTRIBUTING.md](../CONTRIBUTING.md) | Внести изменение: проверки, коммиты, обновление цифр |
| [SECURITY.md](../SECURITY.md) | Сообщить об уязвимости |

## Справка

| Документ | Что внутри |
|---|---|
| [openapi.json](openapi.json) | Снимок спецификации OpenAPI 3.1, сверяется с приложением тестом |
| [API_ERRORS.md](API_ERRORS.md) | Коды ошибок API и классы RFC 9457 |
| [REQUIREMENTS.md](REQUIREMENTS.md) | Каждое исходное требование: где увидеть, где в коде, каким тестом проверено |
| [REQUIREMENTS_QA.md](REQUIREMENTS_QA.md) | Уточнения требований и тесты, которые их доказывают |
| [requirements_trace.md](requirements_trace.md) | 38 автоматических проверок `make accept` |
| [MODEL_CARDS.md](MODEL_CARDS.md) | Карточки моделей и правил: назначение, вход и выход, метрики, выключатель |
| [DATASETS.md](DATASETS.md) | Наборы для валидации, как их получить, SHA-256 |
| [DESIGN.md](DESIGN.md) и [ACCESSIBILITY.md](ACCESSIBILITY.md) | Дизайн-система «Протокол», контраст, проверка доступности |
| [THIRD_PARTY.md](THIRD_PARTY.md) | Сторонние компоненты и лицензии |
| [examples/](examples/ai_raters_result.md) | Примеры файлов разметки и результатов |

## Понять

| Документ | О чём |
|---|---|
| [SOLUTION.md](SOLUTION.md) | Сопроводительная документация: архитектура, механики теста и подбора, валидация, интеграция, API, библиотеки, безопасность |
| [ARCHITECTURE.md](../ARCHITECTURE.md) и [adr/](adr/README.md) | Главные архитектурные решения и их причины |
| [VALIDATION_ASSESSMENT.md](VALIDATION_ASSESSMENT.md) | Проверка теста на грейд: точность, повтор, утечка ключей, экспозиция |
| [VALIDATION_MATCHING.md](VALIDATION_MATCHING.md) | Проверка подбора: базы, доверительные интервалы, абляции, атаки |
| [VALIDATION_INTEGRITY.md](VALIDATION_INTEGRITY.md) и [VALIDATION_NLP.md](VALIDATION_NLP.md) | Сигналы честности теста и разбор резюме |
| [PREREG_MATCHING_2026-10.md](PREREG_MATCHING_2026-10.md) | Предрегистрация эксперимента с подбором (документ не правится задним числом) |
| [TRUST_AND_ATS.md](TRUST_AND_ATS.md) | Защита от фиктивных вакансий, интеграция с ATS, сверка с EU AI Act и NIST AI RMF |
| [THREAT_MODEL.md](THREAT_MODEL.md) и [COMPLIANCE.md](COMPLIANCE.md) | Модель угроз и соответствие 152-ФЗ |
| [BUSINESS.md](BUSINESS.md) | Кто платит и за что, чем продукт отличается от площадок вакансий |
| [BEYOND_TZ.md](BEYOND_TZ.md) и [COMPETITORS.md](COMPETITORS.md) | Что сделано сверх исходных требований и какие идеи взяты из открытых проектов |

## Материалы

| Файл | Что это |
|---|---|
| [FSP_Talent_documentation.pdf](FSP_Talent_documentation.pdf) | Основные документы одним PDF, сборка — `make docs-pdf` |
| [Презентация](../submission/03-presentation/README.md) | PDF и PPTX |
| [Видео 3:17](../submission/05-additional/fsp-talent-demo.mp4) | Запись прохода по кабинету кандидата, подборке и методике |
