"""Complaints pause invitations only when different people complain and the share is not tiny."""
import asyncio
import uuid
from datetime import UTC, datetime

from app.services.trust import should_pause


def test_three_people_among_ten_invitations_pause_the_company():
    assert should_pause(3, 3, 10)


def test_three_complaints_from_one_person_do_not_pause():
    assert not should_pause(1, 3, 10)


def test_three_complaints_among_a_hundred_invitations_stay_under_the_bound():
    assert not should_pause(3, 3, 100)


def test_paused_company_cannot_send_an_invitation(monkeypatch):
    from types import SimpleNamespace

    from app.api.errors import ApiError
    from app.api.v1.offers import OfferCreate, _create_offer

    async def quiet(*_args, **_kwargs):
        return False

    monkeypatch.setattr("app.api.v1.offers.too_many", quiet)
    employer_id = uuid.uuid4()

    class _Db:
        async def get(self, model, _id):
            if model.__name__ == "Employer":
                return SimpleNamespace(id=employer_id, invites_paused_at=datetime.now(UTC))
            return None

    body = OfferCreate(
        candidate_id=uuid.uuid4(), salary_from_gross=100_000, salary_to_gross=150_000,
        role="backend", contact_method="почта",
    )
    try:
        asyncio.run(_create_offer(body, {"sub": str(employer_id)}, _Db()))
    except ApiError as exc:
        assert exc.status_code == 403
        assert exc.detail == "Приглашения приостановлены до проверки"
        return
    raise AssertionError("приглашение ушло")


def test_a_foreign_invitation_is_not_found():
    from app.api.errors import ApiError
    from app.api.v1.candidates import ComplaintIn, file_complaint
    from app.models.offer import Offer

    mine = uuid.uuid4()
    offer_id = uuid.uuid4()
    offer = Offer(id=offer_id, candidate_id=uuid.uuid4(), employer_id=uuid.uuid4())

    class _Db:
        async def get(self, _model, _id):
            return offer

        def add(self, _row):
            raise AssertionError("чужая жалоба не сохраняется")

    body = ComplaintIn(reason="не_вакансия", offer_id=offer_id)

    async def run():
        await file_complaint(body, {"sub": str(mine)}, _Db())

    try:
        asyncio.run(run())
    except ApiError as exc:
        assert exc.status_code == 404
        return
    raise AssertionError("чужое приглашение нашлось")


def test_a_vacancy_without_an_application_is_not_found():
    from types import SimpleNamespace

    from app.api.errors import ApiError
    from app.api.v1.candidates import ComplaintIn, file_complaint

    mine = uuid.uuid4()
    vacancy_id = uuid.uuid4()

    class _Db:
        async def get(self, _model, _id):
            return SimpleNamespace(id=vacancy_id, is_open=True, employer_id=uuid.uuid4())

        async def scalar(self, _query):
            return None

        def add(self, _row):
            raise AssertionError("жалоба без отклика не сохраняется")

    body = ComplaintIn(reason="не_вакансия", vacancy_id=vacancy_id)

    async def run():
        await file_complaint(body, {"sub": str(mine)}, _Db())

    try:
        asyncio.run(run())
    except ApiError as exc:
        assert exc.status_code == 404
        return
    raise AssertionError("вакансия без отклика нашлась")


def test_complaints_migration_downgrades():
    from pathlib import Path

    text = Path("alembic/versions/0005_complaints.py").read_text(encoding="utf-8")
    downgrade = text.split("def downgrade", 1)[1]
    assert "drop_table(\"complaints\")" in downgrade
    assert "invites_paused_at" in downgrade
