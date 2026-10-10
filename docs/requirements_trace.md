# Прослеживаемость требований

Каждая строка — одна существующая проверка. Команда `python -m app.validation.accept` из папки `backend` (или `make accept`) запускает ровно этот список и печатает «Приёмка зелёная», если все прошли. Число — сколько строк в списке, оно не раздуто.

Живой стенд по-прежнему проверяет `make check` (`tests/smoke_api.py`). Эта команда база не трогает.

| Код | Требование | Проверка |
|---|---|---|
| FR-01 | Согласие на данные отдельно от правил | `test_personal_data_consent_is_a_separate_document` |
| FR-02 | Код подтверждения в письме, не в теме | `test_the_code_stays_in_the_body_and_the_link_token_stays_out_of_the_query` |
| FR-03 | Несовершеннолетний без согласия скрыт | `test_discoverable_hides_minors_without_consent_and_hidden_profiles` |
| FR-04 | Тест не понижает подтверждённый грейд | `test_test_never_lowers_a_confirmed_grade` |
| FR-05 | Тест по вакансии не меняет грейд | `test_vacancy_test_never_changes_the_grade` |
| FR-06 | Нет истории ФСП — не штраф | `test_no_fsp_history_is_neutral_not_a_penalty` |
| FR-07 | Результат ФСП не снижает балл | `test_fsp_never_lowers_score` |
| FR-08 | Подтверждённый грейд выше заявленного | `test_confirmed_grade_outranks_declared_grade_at_the_same_skills` |
| FR-09 | Соседняя технология даёт часть балла | `test_missing_skill_is_a_minus_and_related_tech_gets_partial_credit` |
| FR-10 | Вилка двигает место, только если её назвали обе стороны | `test_salary_changes_rank_only_when_both_sides_named_a_band` |
| FR-11 | Сравнение без имени | `test_compare_stays_anonymous` |
| FR-12 | Одно ожидающее приглашение на пару | `test_offer_terms_stay_immutable_and_one_pending_pair_is_unique` |
| FR-13 | Просроченные приглашения закрываются все | `test_every_stale_offer_expires_not_only_the_first` |
| NFR-01 | Новый пароль — Argon2id | `test_argon2id_does_not_store_the_password` |
| NFR-02 | Старый bcrypt переписывается | `test_an_old_bcrypt_hash_still_matches_and_asks_to_be_rewritten` |
| NFR-03 | Cookie сессии требует тот же CSRF-токен | `test_a_cookie_refresh_needs_the_same_csrf_token` |
| NFR-04 | Refresh не попадает в тело ответа браузеру | `test_the_browser_does_not_receive_the_refresh_token_in_the_body` |
| NFR-05 | Классы ошибок E01–E20 покрывают все коды | `test_every_code_belongs_to_one_of_twenty_classes` |
| NFR-06 | Ошибка отдаётся как RFC 9457 | `test_an_error_is_problem_json_and_keeps_the_old_fields` |
| NFR-07 | Каждый код ошибки описан | `test_every_raised_code_is_registered_and_documented` |
| NFR-08 | Список путей OpenAPI совпадает с кодом | `test_openapi_paths_match_the_snapshot` |
| NFR-09 | Ответ 429 содержит Retry-After | `test_a_429_without_its_own_header_still_says_retry_after` |
| NFR-10 | Токен без подписи отвергается | `test_unsigned_token_is_rejected` |
| TC-01 | Короткий пробный тест не подтверждает грейд | `test_express_stops_on_its_count_and_does_not_confirm_a_grade` |
| TC-02 | Случайные ответы не проходят грейд | `test_random_guessing_does_not_pass` |
