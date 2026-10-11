# Карточка данных валидации

Все цифры качества в README и VALIDATION_* получены на этих наборах. Данных людей среди них нет: кандидаты и потребности сгенерированы кодом, разметку пар делали ИИ-оценщики. Хэш позволяет проверить, что набор тот же самый, что и при публикации цифр.

Проверка хэшей файлов: `sha256sum <путь>` из корня репозитория.

## Наборы, которые генерирует код

| Набор | Как получить | Размер | SHA-256 |
|---|---|---|---|
| Подбор: кандидаты и потребности | `cd backend && python -m app.validation.matching` (печатает `sha256` в конце); функция `make_dataset()` в `backend/app/validation/matching.py`, зерно 2026 | 800 кандидатов, 80 потребностей | `1ebff9bbea1c3a3efa08684a86e3094bc6ec88a1867014ad655e9bd12ffc7e00` (Linux x86-64, Python 3.12) |
| Тест: синтетические кандидаты | `cd backend && python -m app.validation.assessment --n 2000 --seed 7`; функция `population()` в `backend/app/validation/assessment.py` | 2000 человек на когорту | хэша нет: набор целиком задаётся зерном и кодом коммита |

Хэш набора подбора считается по JSON с отсортированными ключами. На другой платформе последние знаки чисел с плавающей точкой могут отличаться, тогда отличится и хэш.

## Файлы в репозитории

| Файл | Что внутри | Строк | SHA-256 |
|---|---|---|---|
| `backend/app/validation/resources/jury_profiles.csv` | профили для пакета жюри | — | `ce284459c07b2a151047d1649f06ec404f9b92b10af0f2f40afbd623706e8e46` |
| `backend/app/validation/resources/jury_profiles.json` | те же профили в JSON | — | `a942715c3e92053ac24b45a21b099d14b0d2ec9daf7be0a435ff7c6d2ba3963e` |
| `backend/app/validation/resources/nlp_vacancies_gold.json` | вакансии с эталонной разметкой навыков | — | `7a15ad26261e70b0434b5c15b4b296dfb0c7827cf8b43cf35f4dce42c8172878` |
| `backend/app/validation/resources/nlp_vacancies_holdout.json` | отложенные вакансии для проверки разбора | — | `1f9a01121b430a012a836098c3f9fa1a4a9daea884bb35e54e3c9142fa012066` |
| `docs/examples/blind_pairs_2029.csv` | пары «потребность — кандидат» для слепой разметки | 200 + заголовок | `9ad4e1b87d75697d631f760d670ba844b2eadb9627c3800a18024df34e0c6083` |
| `docs/examples/blind_pairs_2029.key.json` | ключ к слепым парам | — | `bfc9e4f969b7a2ad741131f13c7a0f56c68ea0ebfe8e9128da5d48204222f6da` |
| `docs/examples/ai_rater_a.csv` | разметка ИИ-оценщика A | 200 + заголовок | `4f04898f43adbebe78ae1e1400289db87aecde19bc2f9ad5046b3d818ee1545b` |
| `docs/examples/ai_rater_b.csv` | разметка ИИ-оценщика B | 200 + заголовок | `da61156af7268d4bcf429c8cb89d4b8cd7fdf297fca2aa07611437e2c8f59d67` |
| `docs/examples/ai_raters_merged.jsonl` | сведённая разметка двух оценщиков | 200 | `e8b206eaac0c7064dcd518dbbd4074bf245986df7cf11f105dd4d0f090daadf1` |
| `docs/examples/jury_pairs.jsonl` | пример пар для режима «Разметить самому» | 3 | `b1f93cdf9555cd964a3f7f0f57d4e0fbec882aa981446155b04ec0e29876dce6` |

Хэши посчитаны на коммите `00536e5`. Если файл поменяют, хэш в этой таблице нужно обновить в том же PR.

## Ограничения

- Всё синтетическое. Цифры показывают, как механика ведёт себя на моделях, которые мы сами задали, а не на рынке.
- Разметка пар — ИИ-оценщики, а не люди. Подробности и согласие оценщиков — в `docs/examples/ai_raters_result.md`.
- Внешних открытых наборов в проверке нет.
