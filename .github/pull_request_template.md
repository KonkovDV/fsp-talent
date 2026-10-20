## Что и зачем

<!-- Одна-две фразы: что меняется и почему. Ссылка на Issue: Closes #… -->

## Как проверено

<!-- Команды и результат. Для интерфейса — снимок экрана до и после. -->

## Чек-лист

- [ ] Заголовок по Conventional Commits (`feat:`, `fix:`, `docs:`, `test:`, `refactor:`, `chore:`, `ci:`)
- [ ] `ruff check backend/app backend/seed backend/tests` и юнит-тесты backend проходят
- [ ] Для интерфейса: `npm run type-check`, `npm test` и `npm run build` проходят
- [ ] Если сдвинулись опубликованные цифры, они обновлены и `python tests/doc_numbers.py` согласен
- [ ] Если менялись маршруты API, обновлён `docs/openapi.json` (`python -m app.tools.dump_openapi`)
- [ ] Правила продукта из [CONTRIBUTING.md](https://github.com/KonkovDV/fsp-talent/blob/main/CONTRIBUTING.md#правила-продукта) не нарушены или изменение обсуждено в Issue
- [ ] В изменении нет секретов и настоящих персональных данных
