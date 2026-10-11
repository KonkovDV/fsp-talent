"""A person's own data, for the access right in 152-FZ.

The file is only what this account already sees. Password hashes, session counters and
answer keys of the item bank stay out.
"""
from __future__ import annotations

SECRET_KEYS = frozenset({
    "password_hash", "token_epoch", "refresh_nonce", "code_hash", "token_hash",
})


def _iso(value) -> str | None:
    return value.isoformat() if value else None


def without_secrets(value):
    """Drop secret field names at every level. A nested hash must not ride along in a dump."""
    if isinstance(value, dict):
        return {key: without_secrets(item) for key, item in value.items() if key not in SECRET_KEYS}
    if isinstance(value, list):
        return [without_secrets(item) for item in value]
    return value


def participant_record(person, skills, category, consents, offers,
                      results=(), applications=(), tasks=(), access=()) -> dict:
    return {
        "kind": "participant",
        "email": person.email,
        "display_name": person.display_name,
        "region": person.region,
        "show_city": person.show_city, "show_stack": person.show_stack,
        "show_fsp": person.show_fsp, "show_experience": person.show_experience,
        "phone": person.phone,
        "telegram": person.telegram,
        "fsp_id": person.fsp_id,
        "specialization": person.specialization,
        "declared_grade": person.declared_grade,
        "assessed_grade": person.assessed_grade,
        "experience_years": person.experience_years,
        "salary_from": person.salary_from_gross,
        "salary_to": person.salary_to_gross,
        "is_visible": person.is_visible,
        "job_search": person.job_search,
        "birth_date": _iso(person.birth_date),
        "is_minor": person.minor_now(),
        "minor_consent_given": person.minor_consent_given,
        "guardian_email": person.guardian_email,
        "guardian_consent_at": _iso(person.guardian_consent_at),
        "public_profile": person.public_profile,
        "category": None if category is None else {
            "role": category.primary_role,
            "grade": category.grade,
            "grade_source": category.grade_source,
        },
        "skills": [{"name": skill.name, "trust_level": skill.trust_level,
                    "test_share": getattr(skill, "test_share", None), "test_items": getattr(skill, "test_items", None),
                    "tested_at": skill.tested_at.isoformat() if getattr(skill, "tested_at", None) else None}
                   for skill in skills],
        "consents": [_consent(row) for row in consents],
        "offers": [_candidate_offer(offer) for offer in offers],
        "results": [_result(row) for row in results],
        "applications": [_application(row) for row in applications],
        "tasks": [_task(row) for row in tasks],
        "access": [_access(row) for row in access],
    }


def employer_record(company, consents, vacancies, offers, names_ok: dict | None = None) -> dict:
    return {
        "kind": "employer",
        "email": company.email,
        "company_name": company.company_name,
        "inn": company.inn,
        "website": company.website,
        "industry": company.industry,
        "description": company.description,
        "consents": [_consent(row) for row in consents],
        "vacancies": [{
            "title": vacancy.title,
            "role": vacancy.role,
            "grade": vacancy.grade,
            "skills": list(vacancy.skills or []),
            "salary_from": vacancy.salary_from_gross,
            "salary_to": vacancy.salary_to_gross,
            "is_open": vacancy.is_open,
        } for vacancy in vacancies],
        "offers": [_employer_offer(offer, names_ok) for offer in offers],
    }


def _consent(row) -> dict:
    return {
        "kind": row.kind,
        "version": row.version,
        "given_at": _iso(row.given_at),
        "withdrawn_at": _iso(row.withdrawn_at),
    }


def _candidate_offer(offer) -> dict:
    company = offer.employer.company_name if offer.employer is not None else None
    return {
        "company": company,
        "role": offer.role,
        "status": offer.status,
        "salary_from": offer.salary_from_gross,
        "salary_to": offer.salary_to_gross,
        "created_at": _iso(offer.created_at),
    }


def _result(row) -> dict:
    return {
        "event_name": row.event_name,
        "discipline": row.discipline,
        "place": row.place,
        "event_date": row.event_date.isoformat() if row.event_date else None,
    }


def _application(row) -> dict:
    vacancy = row.vacancy
    return {
        "vacancy": vacancy.title if vacancy is not None else None,
        "status": row.status,
        "created_at": _iso(row.created_at),
    }


def _task(row) -> dict:
    task = row.task
    return {
        "title": task.title if task is not None else None,
        "status": row.status,
        "passed": row.passed,
        "submitted_at": _iso(row.submitted_at),
    }


def _access(row) -> dict:
    company = row.employer.company_name if row.employer is not None else None
    return {
        "company": company,
        "access_type": row.access_type,
        "at": _iso(row.timestamp),
    }


def _employer_offer(offer, names_ok: dict | None) -> dict:
    allowed = True if names_ok is None else bool(names_ok.get(getattr(offer, "candidate_id", None)))
    revealed = offer.contacts_revealed_at is not None and offer.contacts_revoked_at is None and allowed
    name = None
    if revealed and offer.candidate is not None:
        name = offer.candidate.display_name
    return {
        "role": offer.role,
        "status": offer.status,
        "salary_from": offer.salary_from_gross,
        "salary_to": offer.salary_to_gross,
        "created_at": _iso(offer.created_at),
        "candidate_name": name,
    }


def password_change_problem(has_password: bool, current_ok: bool, same_as_current: bool) -> str | None:
    """None when the change may proceed. The codes are for the API, not for the user."""
    if not has_password:
        return "no_password"
    if not current_ok:
        return "bad_current"
    if same_as_current:
        return "same"
    return None
