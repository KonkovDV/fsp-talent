# Решения организаторов → где это в продукте

Сессия «Вопросы и ответы» и письменные ответы организаторов трека уточнили ТЗ. Ниже каждое решение и то, чем его можно проверить: имя теста (`pytest -k <имя>` из папки `backend`), модуль или документ. Если решение не реализовано, так и написано. Все имена тестов и пути в этом файле проверяет `backend/tests/unit/test_organizer_decisions_doc.py`: переименуете тест — упадёт CI.

## Тест, грейд, категория

| Решение | Как у нас | Чем проверить |
|---|---|---|
| Грейд — уровень навыков, подтверждённый тестом; стаж — атрибут профиля | Грейд меняет только тест по специализации; стаж и резюме — подсказка | `test_test_never_lowers_a_confirmed_grade`, `test_test_at_a_grade_never_assigns_a_higher_one` |
| Тест по вакансии не меняет грейд | Тест под вакансию — отдельный блок, грейд не трогает | `test_vacancy_test_never_changes_the_grade` |
| Без теста грейд «не подтверждён», показывать со статусом, ниже подтверждённых | Заявленный грейд виден со статусом и уступает подтверждённому при тех же навыках | `test_confirmed_grade_outranks_declared_grade_at_the_same_skills`, `test_a_declared_grade_does_not_open_a_graded_vacancy` |
| Повышение — отдельным тестом, не автопрыжок; не скакать по грейдам | Отдельный тест на грейд выше, после него пауза; первое подтверждение паузу не запускает | `test_separate_test_at_higher_grade_raises_grade_and_starts_cooldown`, `test_first_confirmation_does_not_start_the_cooldown`, `test_repeat_of_same_grade_does_not_restart_cooldown` |
| Единый тест под категорию, но не одинаковые задания у всех | Параметрические семейства: у каждого свой вариант; ключи проверены исполнением | `test_items_are_practically_unique`, `test_same_seed_gives_the_same_session_and_a_new_seed_fresh_items`, `backend/app/validation/key_check.py` |
| Проверка на списывание не обязательна, но плюс | Сигналы честности и person-fit, кривые «поймано / ложно» | `test_person_fit_flags_answers_the_estimate_cannot_explain`, `test_leak_is_caught_more_often_than_honest_at_product_point`, `docs/VALIDATION_INTEGRITY.md` |
| Экспресс-тест на 3–5 минут допустим | Экспресс-режим, грейд не подтверждает | `test_express_stops_on_its_count_and_does_not_confirm_a_grade` |
| Несколько категорий у кандидата — плюс, не обязательно | Категория из опроса — основная. Другую специализацию кандидат подтверждает отдельным тестом (своя запись подтверждения, своя пауза). Работодатель находит его по этой роли и грейду, на карточке показана подходящая категория, основная рядом. На главной кандидата — блок «Дополнительные категории». Ограничение: без теста вторая категория не появляется, опрос хранит одну специализацию | `test_the_need_role_uses_its_own_confirmation`, `backend/tests/unit/test_second_category.py`, `frontend/src/components/__tests__/OtherCategories.test.tsx` |
| Задания работодателя: адресно, способ оценки — на команде | Адресные задания видит только адресат и автор | `test_addressed_task_is_only_for_its_candidate`, `test_another_employer_does_not_read_the_task` |

## ФСП и ФСП ID

| Решение | Как у нас | Чем проверить |
|---|---|---|
| ФСП — буст внутри подтверждённого грейда, не замена теста | Ось ФСП только поднимает, на грейд не влияет | `test_fsp_never_lowers_score`, `test_fsp_history_boosts_but_never_gates_a_vacancy`, `docs/adr/0003-fsp-axis-only-lifts.md` |
| Корректная работа без истории ФСП | Нет истории — нейтрально, не штраф | `test_no_fsp_history_is_neutral_not_a_penalty`, `test_candidate_without_fsp_is_told_the_axis_does_not_penalise` |
| Учитывать результативность, чтобы профиль не набить явками | Много участий не обгоняют несколько побед | `test_many_participations_do_not_beat_a_few_wins` |
| Keycloak не поднимать, вход имитировать | Мок ФСП ID только на демо-стенде | `test_mock_fsp_id_is_refused_outside_the_demo`, `test_demo_flow_links_the_fsp_id_confirmed_by_the_provider`, `docs/FSP_INTEGRATION.md` |

## Подбор и контакт

| Решение | Как у нас | Чем проверить |
|---|---|---|
| Качество подбора важнее скорости | Своя процедура валидации подбора, предрегистрация | `docs/VALIDATION_MATCHING.md`, `docs/PREREG_MATCHING_2026-10.md` |
| Свой набор пар «потребность — кандидат» | Импорт своей разметки и пересчёт метрик | `backend/app/validation/matching.py` |
| До принятия закрыты только контакты | Контакты и переписка — после принятия приглашения | `test_contacts_wait_for_acceptance`, `test_messages_open_after_accept` |
| Одно адресное приглашение | Условия неизменны, одно ожидающее на пару | `test_offer_terms_stay_immutable_and_one_pending_pair_is_unique` |
| Зарплата: подписать gross или net | Вилка хранится до вычета налога | `test_an_invite_typed_take_home_is_stored_before_tax` |
| Вилка влияет, только если её назвали | Место двигает, только если вилку назвали обе стороны | `test_salary_changes_rank_only_when_both_sides_named_a_band` |
| ATS — в MVP концепция | Подписанные вебхуки, описание приёмника | `docs/TRUST_AND_ATS.md` |

## Право, стенд, сдача

| Решение | Как у нас | Чем проверить |
|---|---|---|
| Правовой минимум — 152-ФЗ | Отдельное согласие, отзыв, выгрузка, удаление | `test_personal_data_consent_is_a_separate_document`, `test_a_withdrawn_distribution_consent_takes_the_person_out`, `docs/COMPLIANCE.md` |
| С 15 лет — согласие родителей | Несовершеннолетний без согласия скрыт | `test_discoverable_hides_minors_without_consent_and_hidden_profiles`, `docs/adr/0010-minors-guardian-consent.md` |
| Стенд без GPU | Базовый compose не требует GPU | `test_base_compose_requests_no_gpu` |
| Десятки одновременных пользователей | Нагрузочный прогон | `docs/LOAD_TEST.md` |
| LLM можно, описать какие и зачем | Карточки моделей, локальный запасной путь | `test_local_fallback_needs_an_explicit_opt_out`, `docs/MODEL_CARDS.md`, `docs/adr/0005-cloud-llm-rules-fallback.md` |
| Данные — свои, парсинг не как механика | Синтетические демо-данные | `docs/DATASETS.md` |
| Обязательный перечень документации | Сдача по пунктам ТЗ | `docs/REQUIREMENTS.md`, `submission/README.md` |
