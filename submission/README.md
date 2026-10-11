# Сдача решения: ФСП Талант

**Задача:** «Цифровая платформа-агрегатор ИТ-вакансий с верифицированным профилем достижений участника ФСП2026».
**Команда:** «ФСП Талант».
**Репозиторий:** [KonkovDV/fsp-talent](https://github.com/KonkovDV/fsp-talent). К моменту сдачи он публичный.

## Пять полей формы

| Поле | Ссылка для формы |
|---|---|
| Репозиторий* | https://github.com/KonkovDV/fsp-talent |
| Документация* | https://github.com/KonkovDV/fsp-talent/tree/main/submission/02-documentation |
| Презентация* | https://github.com/KonkovDV/fsp-talent/tree/main/submission/03-presentation |
| Прототип* | https://github.com/KonkovDV/fsp-talent/tree/main/submission/04-prototype — стенд https://89-124-65-102.sslip.io, зеркало https://v1081358.hosted-by-vdsina.com, демо-входы, проверка за 2 минуты, локальный запуск |
| Дополнительные материалы | https://github.com/KonkovDV/fsp-talent/tree/main/submission/05-additional |

Если поле просит файл, а не ссылку, берём его из той же папки: документация — `02-documentation/FSP_Talent_documentation.pdf`, презентация — `03-presentation/FSP_Talent.pdf`.

| Папка | Что внутри |
|---|---|
| [`01-repository/`](01-repository/README.md) | Ссылка на репозиторий, стек, запуск одной командой, где тесты |
| [`02-documentation/`](02-documentation/README.md) | PDF со всей документацией и список документов в `docs/` |
| [`03-presentation/`](03-presentation/README.md) | Презентация в PDF, PPTX и HTML |
| [`04-prototype/`](04-prototype/README.md) | Стенд, зеркало, демо-входы по ролям, проверка за 2 минуты, локальный запуск |
| [`05-additional/`](05-additional/README.md) | Видео-демо, отчёты проверок, трассировка ТЗ, спецификация API |

## Перед отправкой

- [ ] Репозиторий публичный: ссылки выше открываются в окне без входа в GitHub.
- [ ] PDF документации пересобран (`make docs-pdf`) и его копия лежит в `02-documentation/`.
- [ ] Стенд отвечает: https://89-124-65-102.sslip.io/health возвращает `"status":"ok"`, вход `jury1@demo.talent` / `demo12345` проходит.
- [ ] Ссылка на видео-демо вписана в [`05-additional/README.md`](05-additional/README.md).
