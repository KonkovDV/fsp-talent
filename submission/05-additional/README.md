# Дополнительные материалы

| Материал | Ссылка |
|---|---|
| Видео-демо | [Демо-видео, 3:17, MP4 H.264 1280×800, 7,4 МБ](fsp-talent-demo.mp4) · https://github.com/KonkovDV/fsp-talent/blob/main/submission/05-additional/fsp-talent-demo.mp4 |
| Проверка теста на грейд | [VALIDATION_ASSESSMENT.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/VALIDATION_ASSESSMENT.md) |
| Проверка подбора | [VALIDATION_MATCHING.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/VALIDATION_MATCHING.md) |
| Риск нечестного прохождения теста | [VALIDATION_INTEGRITY.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/VALIDATION_INTEGRITY.md) |
| Разбор резюме и вакансий | [VALIDATION_NLP.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/VALIDATION_NLP.md) |
| Решения организаторов → тесты | [ORGANIZER_DECISIONS.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/ORGANIZER_DECISIONS.md) |
| Трассировка требований ТЗ к проверкам | [requirements_trace.md](https://github.com/KonkovDV/fsp-talent/blob/main/docs/requirements_trace.md), запуск — `make accept` |
| Спецификация API (OpenAPI 3.1) | [openapi.json](https://github.com/KonkovDV/fsp-talent/blob/main/docs/openapi.json), живая версия — https://89-124-65-102.sslip.io/openapi.json |

На видео (запись со стенда под `fsp001`): кабинет кандидата, подборка HR по потребности и страница «Как устроен тест». Кадры — в [video-frames/](video-frames/).

## Что мы измерили и где границы

- Тест на грейд, 2000 синтетических кандидатов: точность решения вдали от границы 91,7 %, случайное угадывание проходит тест в 0 % случаев (`python -m app.validation.assessment --n 2000 --seed 7`).
- Подбор на трёх зёрнах: P@10 0,636 против 0,559 у сортировки по резюме, Спирмен внутри категории 0,374 против 0,011 (`python -m app.validation.matching`).
- Ключи заданий проверены запуском: 1875 из 1875 вариантов совпали с ключом, 25 на Java не проверены (`python -m app.validation.key_check --variants 20`).
- Повтор всей процедуры: κw двух путей 0,85 (зёрна 201–205; при старом порядке шкалы 0,76), тот же грейд у 65,2 %, тот же или соседний у 99,7 % (`python -m app.validation.assessment --n 2000 --seed S`).
- Завышенный в анкете грейд не подтверждён в 92,6 %; «сдал / не сдал» верно в 77,8 % против 71,5 % у «верить анкете» (`... --parity`).
- Подбор по градуированным протоколам: nDCG@10 0,621 (A) и 0,684 (B), у BM25 по протоколу A 0,399 (`python -m app.validation.matching --protocol all`).
- Сигналы честности на пороге продукта: поймано 90,0 % сессий с утечкой, ложно 0,7 % (`python -m app.validation.detector_curves`). EAP против WLE: κw 0,925 и 0,929 (`python -m app.validation.wle_eap --n 2000`).
- Подъём оси ФСП на отложенных зёрнах меняет nDCG@10 на −0,015 (95 % ДИ −0,0195…−0,0104). Подъём включён по нормативной причине (ТЗ 2.1): он поднимает подтверждённых участников внутри категории; величину подъёма перекалибруем на разметке пилота ([подробно](https://github.com/KonkovDV/fsp-talent/blob/main/docs/VALIDATION_MATCHING.md#подъём-оси-фсп)).
- Нагрузка: 40 пользователей одновременно, 0 ошибок, p95 поиска 69 мс (`make load`).
- Всё это посчитано на синтетике со скрытой правдой и замерено на стенде. Результат на живых участниках ФСП даст пилот, сертификацией эти цифры не являются.
