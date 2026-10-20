"""What withdrawing one consent does. The codes are stable; the text is for the person."""
from __future__ import annotations


def planned_effects(role: str, kind: str) -> list[dict[str, str]]:
    if role == "participant" and kind == "pd_candidate":
        return [
            {"code": "hide_card", "text": "Карточка сразу пропадёт из поиска."},
            {"code": "close_contacts",
             "text": "Компании перестанут видеть уже открытые контакты, а их ATS получат требование удалить их."},
            {"code": "erase_in_30_days",
             "text": "Имя, контакты и навыки будут стёрты в течение 30 дней (ч. 5 ст. 21 152-ФЗ), "
                     "если закон не требует их хранить."},
        ]
    if role == "participant" and kind == "pd_distribution":
        return [
            {"code": "public_page_off",
             "text": "Публичная страница выключится. Карточка в поиске от этого согласия не зависит."},
            {"code": "fsp_lookup_off",
             "text": "Вы пропадёте из рейтинга, а по ФСП ID ваши протоколы больше не найдутся."},
        ]
    if role == "employer" and kind == "pd_employer":
        return [
            {"code": "stop_processing",
             "text": "Обработка данных компании остановится. Уже отправленные приглашения у кандидатов останутся."},
        ]
    if kind == "terms":
        return [
            {"code": "rules_withdrawn",
             "text": "Согласие с правилами будет отозвано. Согласие на обработку данных отзывается отдельно."},
        ]
    return [{"code": "record_only", "text": "Отзыв запишется в журнал. Другие данные от этого документа не зависят."}]
