"""One acceptance run: the checks named in docs/requirements_trace.md.

    python -m app.validation.accept

Each row is an existing unit test. The command does not invent checks and does not touch the database.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

CHECKS: tuple[tuple[str, str, str], ...] = (
    ("FR-01", "Согласие на данные отдельно от правил",
     "tests/unit/test_identity.py::test_personal_data_consent_is_a_separate_document"),
    ("FR-02", "Код подтверждения в письме, не в теме",
     "tests/unit/test_identity.py::test_the_code_stays_in_the_body_and_the_link_token_stays_out_of_the_query"),
    ("FR-03", "Несовершеннолетний без согласия скрыт",
     "tests/unit/test_security.py::test_discoverable_hides_minors_without_consent_and_hidden_profiles"),
    ("FR-04", "Тест не понижает подтверждённый грейд",
     "tests/unit/test_assessment_policy.py::test_test_never_lowers_a_confirmed_grade"),
    ("FR-05", "Тест по вакансии не меняет грейд",
     "tests/unit/test_assessment_policy.py::test_vacancy_test_never_changes_the_grade"),
    ("FR-06", "Нет истории ФСП — не штраф",
     "tests/unit/test_matching.py::test_no_fsp_history_is_neutral_not_a_penalty"),
    ("FR-07", "Результат ФСП не снижает балл",
     "tests/unit/test_matching.py::test_fsp_never_lowers_score"),
    ("FR-08", "Подтверждённый грейд выше заявленного",
     "tests/unit/test_matching.py::test_confirmed_grade_outranks_declared_grade_at_the_same_skills"),
    ("FR-09", "Соседняя технология даёт часть балла",
     "tests/unit/test_matching.py::test_missing_skill_is_a_minus_and_related_tech_gets_partial_credit"),
    ("FR-10", "Вилка двигает место, только если её назвали обе стороны",
     "tests/unit/test_matching.py::test_salary_changes_rank_only_when_both_sides_named_a_band"),
    ("FR-11", "Сравнение без имени",
     "tests/unit/test_matching.py::test_compare_stays_anonymous"),
    ("FR-12", "Одно ожидающее приглашение на пару",
     "tests/unit/test_security.py::test_offer_terms_stay_immutable_and_one_pending_pair_is_unique"),
    ("FR-13", "Просроченные приглашения закрываются все",
     "tests/unit/test_offer_expiry.py::test_every_stale_offer_expires_not_only_the_first"),
    ("NFR-01", "Новый пароль — Argon2id",
     "tests/unit/test_security.py::test_argon2id_does_not_store_the_password"),
    ("NFR-02", "Старый bcrypt переписывается",
     "tests/unit/test_security.py::test_an_old_bcrypt_hash_still_matches_and_asks_to_be_rewritten"),
    ("NFR-03", "Cookie сессии требует тот же CSRF-токен",
     "tests/unit/test_security.py::test_a_cookie_refresh_needs_the_same_csrf_token"),
    ("NFR-04", "Refresh не попадает в тело ответа браузеру",
     "tests/unit/test_security.py::test_the_browser_does_not_receive_the_refresh_token_in_the_body"),
    ("NFR-05", "Классы ошибок E01–E20 покрывают все коды",
     "tests/unit/test_problems.py::test_every_code_belongs_to_one_of_twenty_classes"),
    ("NFR-06", "Ошибка отдаётся как RFC 9457",
     "tests/unit/test_problems.py::test_an_error_is_problem_json_and_keeps_the_old_fields"),
    ("NFR-07", "Каждый код ошибки описан",
     "tests/unit/test_identity.py::test_every_raised_code_is_registered_and_documented"),
    ("NFR-08", "Список путей OpenAPI совпадает с кодом",
     "tests/unit/test_openapi_paths.py::test_openapi_paths_match_the_snapshot"),
    ("NFR-09", "Ответ 429 содержит Retry-After",
     "tests/unit/test_security.py::test_a_429_without_its_own_header_still_says_retry_after"),
    ("NFR-10", "Токен без подписи отвергается",
     "tests/unit/test_security.py::test_unsigned_token_is_rejected"),
    ("TC-01", "Короткий пробный тест не подтверждает грейд",
     "tests/unit/test_assessment_policy.py::test_express_stops_on_its_count_and_does_not_confirm_a_grade"),
    ("TC-02", "Случайные ответы не проходят грейд",
     "tests/unit/test_assessment_policy.py::test_random_guessing_does_not_pass"),
    ("AUD-01", "GPU не нужен: базовый compose без видеокарты (M-5)",
     "tests/unit/test_compose_gpu_optional.py::test_base_compose_requests_no_gpu"),
    ("AUD-02", "Токен CI только на чтение (N-6)",
     "tests/unit/test_ci_policy.py::test_workflow_token_is_read_only_by_default"),
    ("AUD-03", "Цитата LLM должна называть навык (N-3)",
     "tests/unit/test_resume_fields.py::test_prompt_injection_cannot_pin_a_skill_to_an_unrelated_quote"),
    ("AUD-04", "Поиск по ФСП ID — только публичный профиль с согласием (H-1)",
     "tests/unit/test_public_pii.py::test_achievements_lookup_requires_public_profile_consent_and_adult"),
    ("AUD-05", "История ФСП никогда не опускает работодательский балл (H-2)",
     "tests/unit/test_fsp_lift_property.py::test_fsp_history_never_lowers_the_employer_score"),
    ("AUD-06", "Новое событие не опускает ось ФСП, участие — не штраф (H-3)",
     "tests/unit/test_fsp_engine_monotone.py::test_adding_any_event_never_lowers_the_bound"),
    ("AUD-07", "Устаревшие баллы пересчитываются при старте",
     "tests/unit/test_rescore_stale.py::test_the_container_rescores_after_schema_sync_and_before_serving"),
    ("AUD-08", "Демо-логины сид не трогает",
     "tests/unit/test_seed_reserved.py::test_no_sql_pattern_on_the_encrypted_email_column"),
    ("AUD-09", "МРОТ 27 093 ₽ в бэкенде, фронте и документах",
     "tests/unit/test_doc_facts.py::test_salary_floor_is_the_2026_minimum_wage_everywhere"),
    ("AUD-10", "Решение Python в песочнице не может форкаться",
     "tests/unit/test_sandbox_hardening.py::test_python_children_get_no_processes"),
    ("AUD-11", "Сокет песочницы не доступен всем",
     "tests/unit/test_sandbox_hardening.py::test_socket_is_owner_and_group_only"),
    ("AUD-12", "Затухание ФСП пересчитывается каждую ночь",
     "tests/unit/test_decay_and_reconcile.py::test_fsp_scores_are_recomputed_every_night"),
    ("AUD-13", "Грейд на границе помечен на карточке (NEW-2)",
     "tests/unit/test_borderline_badge.py::test_card_carries_the_flag_only_for_the_assessed_header_grade"),
)


def missing_nodes() -> list[str]:
    """Checks whose test function is not in the named file."""
    missing = []
    for code, _title, node in CHECKS:
        path, _, name = node.partition("::")
        text = (ROOT / path).read_text(encoding="utf-8")
        if f"def {name}" not in text:
            missing.append(code)
    return missing


def main() -> int:
    missing = missing_nodes()
    if missing:
        print("Нет таких проверок:", ", ".join(missing))
        return 2
    print(f"Приёмка: {len(CHECKS)} проверок", flush=True)
    nodes = [node for _code, _title, node in CHECKS]
    completed = subprocess.run(
        [sys.executable, "-m", "pytest", "-q", "--tb=line", "-p", "no:cacheprovider", *nodes],
        cwd=ROOT,
    )
    if completed.returncode == 0:
        print(f"Приёмка зелёная: {len(CHECKS)}", flush=True)
    return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
