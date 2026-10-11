# Дополнительные материалы

| Материал | Ссылка |
|---|---|
| Видео-демо | [Демо-видео, 3:17](fsp-talent-demo.mp4) · https://github.com/KonkovDV/fsp-talent/blob/main/submission/05-additional/fsp-talent-demo.mp4 |
| Проверка теста на грейд | [VALIDATION_ASSESSMENT.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/VALIDATION_ASSESSMENT.md) |
| Проверка подбора | [VALIDATION_MATCHING.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/VALIDATION_MATCHING.md) |
| Риск нечестного прохождения теста | [VALIDATION_INTEGRITY.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/VALIDATION_INTEGRITY.md) |
| Разбор резюме и вакансий | [VALIDATION_NLP.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/VALIDATION_NLP.md) |
| Трассировка требований ТЗ к проверкам | [requirements_trace.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/requirements_trace.md), запуск — `make accept` |
| Спецификация API (OpenAPI 3.1) | [openapi.json](https://github.com/KonkovDV/fsp-talent/blob/main/docs/openapi.json), живая версия — https://89-124-65-102.sslip.io/openapi.json |

На видео (запись со стенда под `fsp001`): кабинет кандидата, подборка HR по потребности и страница «Как устроен тест». Кадры — в [video-frames/](video-frames/).

## Что измерено и чем это не является

- Тест на грейд, 2000 синтетических кандидатов: точность решения вдали от границы 91,7 %, случайное угадывание проходит тест в 0 % случаев (`python -m app.validation.assessment --n 2000 --seed 7`).
- Подбор на трёх зёрнах: P@10 0,636 против 0,559 у сортировки по резюме, Спирмен внутри категории 0,374 против 0,011 (`python -m app.validation.matching`).
- Нагрузка: 40 пользователей одновременно, 0 ошибок, p95 поиска 69 мс (`make load`).
- Всё это синтетика со скрытой правдой и замер на стенде. Это не результат на живых участниках ФСП и не сертификация.
