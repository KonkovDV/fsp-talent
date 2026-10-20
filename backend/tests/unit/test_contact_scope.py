"""The candidate picks which contacts a company sees; every company-facing output keeps to that choice."""
import uuid
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace

import pytest

from app.api.errors import ApiError
from app.api.v1 import candidates, integrations, offers, vacancies
from app.services.contact_scope import CHANNELS, EmptyScope, available, clean_share, contacts, describe, scope

LATER = datetime.now(UTC) + timedelta(days=7)


def person(**kw):
    fields = dict(id=uuid.uuid4(), display_name="Аня", email="anya@demo.talent", telegram="@anya",
                  phone="+79990000000", github=None, region="Москва", job_search="active")
    fields.update(kw)
    return SimpleNamespace(**fields)


def offer(candidate, **kw):
    fields = dict(id=uuid.uuid4(), employer_id=uuid.uuid4(), candidate_id=candidate.id, role="Backend",
                  status="pending", expires_at=LATER, contacts_revoked_at=None, contacts_revealed_at=None,
                  responded_at=None, counter_note=None, counter_at=None, shared_contacts=None,
                  salary_from_gross=200_000, salary_to_gross=250_000, work_format="remote", decline_reason=None)
    fields.update(kw)
    return SimpleNamespace(**fields)


class Rows(list):
    def all(self):
        return list(self)


class Db:
    def __init__(self, by_model=None, scalars=(), latest=None):
        self.by_model = by_model or {}
        self.rows = list(scalars)
        self.latest = latest
        self.added = []

    async def get(self, model, ident=None, **kwargs):
        return self.by_model.get(model.__name__)

    async def scalar(self, stmt):
        return self.latest

    async def scalars(self, stmt):
        return Rows(self.rows)

    async def execute(self, stmt):
        return SimpleNamespace(rowcount=0)

    def add(self, obj):
        self.added.append(obj)

    async def commit(self):
        pass

    async def rollback(self):
        pass

    def logs(self, event_type):
        return [o for o in self.added if getattr(o, "event_type", None) == event_type]


@pytest.fixture
def wired(monkeypatch):
    sent, notes = [], []

    async def grab(_db, _employer, event_type, payload):
        sent.append((event_type, payload))
        return 0

    async def none(*_args, **_kwargs):
        return 0

    async def yes(*_args, **_kwargs):
        return True

    async def note(_db, _outbox, role, _rid, kind, title, body, link):
        notes.append((role, kind, title, body))

    async def under_limit(*_args, **_kwargs):
        return False

    monkeypatch.setattr("app.services.webhooks.enqueue", grab)
    monkeypatch.setattr("app.services.webhooks.deliver_due", none)
    monkeypatch.setattr("app.services.webhooks.drop_stale_contact_deliveries", none)
    monkeypatch.setattr("app.services.search.cache.publish_invite", none)
    monkeypatch.setattr(candidates, "too_many", under_limit)
    for module in (candidates, offers, integrations, vacancies):
        monkeypatch.setattr(module, "contacts_allowed", yes)
    monkeypatch.setattr(candidates, "notify", note)
    monkeypatch.setattr(offers, "notify", note)
    return SimpleNamespace(sent=sent, notes=notes)


def test_only_filled_channels_can_be_opened_and_the_order_is_fixed():
    anya = person()
    assert available(anya) == ["email", "telegram", "phone"]
    assert clean_share(["phone", "email", "github"], anya) == ["email", "phone"]
    with pytest.raises(EmptyScope):
        clean_share(["github"], anya)
    assert scope(SimpleNamespace(shared_contacts=None)) == list(CHANNELS)
    assert scope(SimpleNamespace(shared_contacts=["telegram", "email"])) == ["email", "telegram"]
    assert contacts(anya, ["telegram"]) == {"email": None, "telegram": "@anya", "phone": None, "github": None}
    assert describe(["phone", "email"]) == "email, телефон"


async def test_accepting_with_a_choice_opens_only_those_channels(wired):
    anya = person()
    row = offer(anya)
    db = Db({"Offer": row, "Participant": anya})
    body = candidates.RespondIn(action="accept", share=["telegram"])
    answer = await candidates.respond_to_offer(row.id, body, {"sub": str(anya.id)}, db)
    assert answer["status"] == "accepted" and row.shared_contacts == ["telegram"]
    [log] = db.logs("contacts_revealed")
    assert log.meta["channels"] == ["telegram"]
    event_type, payload = wired.sent[-1]
    assert event_type == "offer.accepted"
    assert payload["candidate"]["telegram"] == "@anya"
    assert payload["candidate"]["email"] is None and payload["candidate"]["phone"] is None
    assert payload["candidate"]["shared"] == ["telegram"]
    assert "Открыты: Telegram" in wired.notes[-1][3]


async def test_accepting_without_a_choice_freezes_filled_channels(wired):
    anya = person()
    row = offer(anya)
    db = Db({"Offer": row, "Participant": anya})
    await candidates.respond_to_offer(row.id, candidates.RespondIn(action="accept"), {"sub": str(anya.id)}, db)
    assert row.shared_contacts == ["email", "telegram", "phone"]
    payload = wired.sent[-1][1]
    assert payload["candidate"]["email"] == anya.email and payload["candidate"]["phone"] == anya.phone
    assert payload["candidate"]["github"] is None and payload["candidate"]["shared"] == row.shared_contacts


async def test_a_choice_of_empty_channels_is_refused_and_the_invitation_waits(wired):
    anya = person()
    row = offer(anya)
    db = Db({"Offer": row, "Participant": anya})
    with pytest.raises(ApiError) as refused:
        await candidates.respond_to_offer(
            row.id, candidates.RespondIn(action="accept", share=["github"]), {"sub": str(anya.id)}, db)
    assert refused.value.status_code == 422 and row.status == "pending" and wired.sent == []


async def test_yes_if_keeps_the_choice_for_when_the_company_agrees(wired):
    anya = person()
    row = offer(anya)
    db = Db({"Offer": row, "Participant": anya})
    body = candidates.RespondIn(action="yes_if", note="Возьму, если вилка от 280 тысяч", share=["email"])
    await candidates.respond_to_offer(row.id, body, {"sub": str(anya.id)}, db)
    assert row.status == "pending" and row.shared_contacts == ["email"]
    company = SimpleNamespace(id=row.employer_id, company_name="Сибирский код")
    db.by_model["Employer"] = company
    opened = await offers.accept_counter_offer(row.id, {"sub": str(row.employer_id), "role": "employer"}, db)
    assert opened["status"] == "accepted"
    payload = wired.sent[-1][1]
    assert payload["candidate"]["email"] == anya.email
    assert payload["candidate"]["telegram"] is None and payload["candidate"]["phone"] is None
    assert db.logs("contacts_revealed")[-1].meta["channels"] == ["email"]
    assert "Компании открыты: email" in wired.notes[-1][3]


async def test_the_company_cabinet_shows_only_opened_channels(wired):
    anya = person()
    row = offer(anya, status="accepted", shared_contacts=["phone"], contacts_revealed_at=datetime.now(UTC))
    db = Db({"Offer": row, "Participant": anya})
    seen = await offers.reveal_contacts(row.id, {"sub": str(row.employer_id), "role": "employer"}, db)
    assert seen["phone"] == anya.phone and seen["email"] is None and seen["telegram"] is None
    assert seen["display_name"] == "Аня" and seen["shared_contacts"] == ["phone"]
    assert offers._offer_out(SimpleNamespace(
        **{**vars(row), "currency": "RUB", "message": None, "created_at": datetime.now(UTC), "contact_method": None,
           "perks": [], "practice_stage": None, "candidate_viewed_at": None}))["shared_contacts"] == ["phone"]


async def test_the_ats_export_keeps_to_the_choice(wired):
    anya = person()
    row = offer(anya, status="accepted", shared_contacts=["email"])
    db = Db({"Participant": anya}, scalars=[row])
    out = await integrations.export(fmt="json", current={"sub": str(row.employer_id), "role": "employer"}, db=db)
    [item] = out["items"]
    assert item["email"] == anya.email and item["phone"] is None and item["telegram"] is None


async def test_vacancy_applications_follow_the_choice_on_the_accepted_invitation(wired):
    anya = person()
    employer_id = uuid.uuid4()
    latest = offer(anya, employer_id=employer_id, status="accepted", shared_contacts=["telegram"])
    application = SimpleNamespace(id=uuid.uuid4(), vacancy_id=uuid.uuid4(), candidate_id=anya.id, viewed_at=None)
    vacancy = SimpleNamespace(id=application.vacancy_id, employer_id=employer_id)
    db = Db({"Application": application, "Vacancy": vacancy, "Participant": anya}, latest=latest)
    seen = await vacancies.application_contacts(application.id, {"sub": str(employer_id), "role": "employer"}, db)
    assert seen["telegram"] == "@anya" and seen["email"] is None and seen["phone"] is None
    db.latest = None
    seen = await vacancies.application_contacts(application.id, {"sub": str(employer_id), "role": "employer"}, db)
    assert seen["email"] == anya.email and seen["shared_contacts"] == list(CHANNELS)


async def test_narrowing_the_choice_tells_the_company_what_to_delete(wired):
    anya = person()
    row = offer(anya, status="accepted", shared_contacts=["email", "phone"])
    sibling = offer(anya, employer_id=row.employer_id, status="accepted",
                    shared_contacts=["email", "phone", "telegram"])
    db = Db({"Offer": row, "Participant": anya}, scalars=[row, sibling])
    out = await candidates.change_shared_contacts(
        row.id, candidates.ShareIn(share=["email"]), {"sub": str(anya.id)}, db)
    assert out == {"shared_contacts": ["email"]} and row.shared_contacts == ["email"]
    assert sibling.shared_contacts == ["email"]
    [log] = db.logs("contacts_scope_changed")
    assert log.meta["removed"] == ["phone"] and set(log.meta["offers"]) == {str(row.id), str(sibling.id)}
    event_type, payload = wired.sent[-1]
    assert event_type == "contacts.updated"
    assert payload["candidate"]["removed"] == ["phone"] and payload["candidate"]["phone"] is None
    assert "Удалите у себя: телефон" in wired.notes[-1][3]

    wired.sent.clear()
    same = await candidates.change_shared_contacts(
        row.id, candidates.ShareIn(share=["email"]), {"sub": str(anya.id)}, db)
    assert same == {"shared_contacts": ["email"]} and wired.sent == []


async def test_an_old_acceptance_names_only_filled_channels_as_removed(wired):
    anya = person()
    row = offer(anya, status="accepted", shared_contacts=None)
    db = Db({"Offer": row, "Participant": anya})
    same = await candidates.change_shared_contacts(
        row.id, candidates.ShareIn(share=["email", "telegram", "phone"]), {"sub": str(anya.id)}, db)
    assert same == {"shared_contacts": ["email", "telegram", "phone"]}
    assert row.shared_contacts == ["email", "telegram", "phone"] and wired.sent == []
    row.shared_contacts = None
    await candidates.change_shared_contacts(row.id, candidates.ShareIn(share=["email"]), {"sub": str(anya.id)}, db)
    assert wired.sent[-1][1]["candidate"]["removed"] == ["telegram", "phone"]


async def test_erasure_asks_every_holder_to_delete_once(wired):
    from app.services import privacy

    anya = person()
    first, second = uuid.uuid4(), uuid.uuid4()
    db = Db({"Participant": anya}, scalars=[first, second, first])
    assert await privacy.tell_contact_holders(db, anya.id, "account_deleted") == 2
    assert [e for e, _ in wired.sent] == ["contacts.revoked", "contacts.revoked"]
    assert {p["employer_id"] for _, p in wired.sent} == {str(first), str(second)}
    assert all(p["candidate"]["delete"] is True and p["reason"] == "account_deleted" for _, p in wired.sent)
    assert all("email" not in p["candidate"] for _, p in wired.sent)


async def test_withdrawing_consent_asks_holders_to_delete(wired, monkeypatch):
    from starlette.requests import Request

    from app.api.v1 import legal

    async def withdrawn(*_args, **_kwargs):
        return SimpleNamespace(kind="pd_candidate")

    async def nothing(*_args, **_kwargs):
        return None

    monkeypatch.setattr(legal, "withdraw_consent", withdrawn)
    monkeypatch.setattr(legal, "bump_bank_epoch", nothing)
    anya = person(public_profile=False, is_visible=True)
    holder = uuid.uuid4()
    request = Request({"type": "http", "method": "DELETE", "headers": [], "client": ("127.0.0.1", 1)})
    effect = await legal.withdraw("pd_candidate", request, {"sub": str(anya.id), "role": "participant"},
                                  Db({"Participant": anya}, scalars=[holder]))
    assert effect["withdrawn"] is True and anya.is_visible is False
    assert [(e, p["reason"]) for e, p in wired.sent] == [("contacts.revoked", "consent_withdrawn")]
    assert any("ATS" in text for text in effect["effects"])


async def test_the_choice_changes_only_on_an_open_accepted_invitation(wired):
    anya = person()
    waiting = offer(anya)
    closed = offer(anya, status="accepted", contacts_revoked_at=datetime.now(UTC))
    for row in (waiting, closed):
        with pytest.raises(ApiError) as refused:
            await candidates.change_shared_contacts(
                row.id, candidates.ShareIn(share=["email"]), {"sub": str(anya.id)},
                Db({"Offer": row, "Participant": anya}))
        assert refused.value.status_code == 409
    stranger = offer(person())
    with pytest.raises(Exception) as hidden:
        await candidates.change_shared_contacts(
            stranger.id, candidates.ShareIn(share=["email"]), {"sub": str(anya.id)},
            Db({"Offer": stranger, "Participant": anya}))
    assert getattr(hidden.value, "status_code", None) == 404
