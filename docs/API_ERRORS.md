# Коды ошибок API

Любая ошибка возвращается в одном формате:

```json
{"error": {"code": "email_not_verified", "message": "Email не подтверждён: введите код из письма", "details": {"email": "a@b.ru", "role": "participant"}},
 "detail": "Email не подтверждён: введите код из письма"}
```

`detail` оставлен для клиентов, написанных под формат FastAPI по умолчанию. Для ошибок валидации (422) `detail` и `error.details` содержат список полей. У 429 есть заголовок `Retry-After`.

Список ниже сверяется с кодом тестом `tests/unit/test_identity.py`.

| Код | Значение |
|---|---|
| `bad_request` | HTTP 400 |
| `unauthorized` | HTTP 401 |
| `forbidden` | HTTP 403 |
| `not_found` | HTTP 404 |
| `method_not_allowed` | HTTP 405 |
| `conflict` | HTTP 409 |
| `gone` | HTTP 410 |
| `validation_error` | HTTP 422 |
| `rate_limited` | HTTP 429 |
| `internal_error` | HTTP 500 |
| `unavailable` | HTTP 503 |
| `invalid_credentials` | Неверный email или пароль |
| `email_not_verified` | Email не подтверждён: введите код из письма |
| `email_taken` | Аккаунт с таким email уже есть |
| `verification_invalid` | Код или ссылка не подходят |
| `verification_expired` | Срок кода истёк, запросите новый |
| `verification_attempts` | Слишком много неверных попыток, запросите новый код |
| `resend_cooldown` | Новый код можно запросить через минуту |
| `consent_required` | Нужно согласие на обработку данных |
| `consent_unknown` | Нет такого документа |
| `consent_withdrawn` | Кандидат отозвал согласие на обработку данных: контакты недоступны |
| `delete_confirm` | Чтобы удалить аккаунт, введите слово «удалить» |
| `fsp_invalid` | Неверные учётные данные ФСП |
| `fsp_taken` | Этот ФСП ID уже привязан к другому аккаунту |
| `fsp_already_linked` | К аккаунту уже привязан ФСП ID |
| `fsp_not_found` | Протоколы ФСП не найдены |
| `survey_required` | Сначала пройдите опрос: выберите специализацию |
| `grade_locked` | Подтверждённый грейд пока нельзя менять |
| `retake_cooldown` | Пересдача доступна позже |
| `question_bank_empty` | Не хватает заданий для теста |
| `session_closed` | Сессия теста уже завершена |
| `session_expired` | Время сессии истекло |
| `item_token_invalid` | Задание не принадлежит этой сессии |
| `offer_closed` | Приглашение уже обработано |
| `offer_expired` | Срок приглашения истёк |
| `contacts_hidden` | Контакты откроются после согласия кандидата |
| `salary_required` | Укажите зарплатную вилку от и до |
| `need_not_found` | Потребность не найдена |
| `contacts_revoked` | Кандидат закрыл контакты для вашей компании |
| `task_closed` | Задание закрыто или срок сдачи прошёл |
| `task_answered` | Ответ на это задание уже отправлен |
| `fsp_ticket_invalid` | Вход через ФСП ID устарел: начните вход заново |
