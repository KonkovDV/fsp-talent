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
| AUD-01 | GPU не нужен: базовый compose без видеокарты (M-5) | `test_base_compose_requests_no_gpu` |
| AUD-02 | Токен CI только на чтение (N-6) | `test_workflow_token_is_read_only_by_default` |
| AUD-03 | Цитата LLM должна называть навык (N-3) | `test_prompt_injection_cannot_pin_a_skill_to_an_unrelated_quote` |
| AUD-04 | Поиск по ФСП ID — только публичный профиль с согласием (H-1) | `test_achievements_lookup_requires_public_profile_consent_and_adult` |
| AUD-05 | История ФСП никогда не опускает работодательский балл (H-2) | `test_fsp_history_never_lowers_the_employer_score` |
| AUD-06 | Новое событие не опускает ось ФСП, участие — не штраф (H-3) | `test_adding_any_event_never_lowers_the_bound` |
| AUD-07 | Устаревшие баллы пересчитываются при старте | `test_the_container_rescores_after_schema_sync_and_before_serving` |
| AUD-08 | Демо-логины сид не трогает | `test_no_sql_pattern_on_the_encrypted_email_column` |
| AUD-09 | МРОТ 27 093 ₽ в бэкенде, фронте и документах | `test_salary_floor_is_the_2026_minimum_wage_everywhere` |
| AUD-10 | Решение Python в песочнице не может форкаться | `test_python_children_get_no_processes` |
| AUD-11 | Сокет песочницы не доступен всем | `test_socket_is_owner_and_group_only` |
| AUD-12 | Затухание ФСП пересчитывается каждую ночь | `test_fsp_scores_are_recomputed_every_night` |
| AUD-13 | Грейд на границе помечен на карточке (NEW-2) | `test_card_carries_the_flag_only_for_the_assessed_header_grade` |

Строки AUD — исправления аудита 11.10.2026 (`docs/audit/`, PR #238–#255). Ссылки проверяет `tests/unit/test_accept.py`: битая ссылка на тест роняет CI.
