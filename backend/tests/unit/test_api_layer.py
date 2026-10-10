"""Route bodies of the API layer, driven by a scripted session.

The handlers run as they do in the product. The database and Redis are not the stand:
a queue answers get/scalar/execute, and the counters that would write to Redis stay quiet.
"""
import json
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from fastapi import FastAPI, HTTPException
from fastapi.testclient import TestClient
from pydantic import ValidationError
from starlette.requests import Request

from app.api.deps import get_any_auth, get_current_employer, get_current_participant
from app.api.errors import ApiError, install_error_handlers
from app.api.v1 import (
    ai,
    assessment,
    auth,
    candidates,
    employer,
    favorites,
    fsp_id_demo,
    interviews,
    legal,
    messages,
    moderation,
    needs,
    notifications,
    offers,
    public,
    search,
    tasks,
    vacancies,
)
from app.core.config import settings
from app.core.security import create_access_token, create_token
from app.models.employer import Employer
from app.services.fsp.identity import MockFspIdProvider

NOW = datetime(2026, 10, 9, 12, tzinfo=UTC)


class Scalars:
    def __init__(self, rows):
        self._rows = list(rows)

    def __iter__(self):
        return iter(self._rows)

    def all(self):
        return list(self._rows)


class Exec:
    def __init__(self, rows=(), rowcount=1):
        self._rows = list(rows)
        self.rowcount = rowcount

    def __iter__(self):
        return iter(self._rows)

    def all(self):
        return list(self._rows)


class Bag:
    def __init__(self):
        self.gets: list = []
        self.scalars_q: list = []
        self.scalar_q: list = []
        self.execute_q: list = []
        self.added: list = []
        self.commits = 0

    async def get(self, model, ident=None, **kwargs):
        return self.gets.pop(0) if self.gets else None

    async def scalars(self, stmt):
        return Scalars(self.scalars_q.pop(0) if self.scalars_q else [])

    async def scalar(self, stmt):
        return self.scalar_q.pop(0) if self.scalar_q else None

    async def execute(self, stmt):
        item = self.execute_q.pop(0) if self.execute_q else Exec()
        return item if isinstance(item, Exec) else Exec(item)

    def add(self, obj):
        self.added.append(obj)

    async def flush(self):
        for obj in self.added:
            if getattr(obj, "id", None) is None:
                obj.id = uuid.uuid4()
            for name in ("created_at", "updated_at"):
                if hasattr(obj, name) and getattr(obj, name) is None:
                    setattr(obj, name, NOW)

    async def commit(self):
        self.commits += 1
        await self.flush()

    async def refresh(self, obj):
        return None

    async def rollback(self):
        return None

    async def delete(self, obj):
        return None


def _uid() -> uuid.UUID:
    return uuid.uuid4()


def _current(role: str, subject: uuid.UUID | None = None) -> dict:
    return {"sub": str(subject or _uid()), "role": role}


def _person(**extra):
    fields = dict(
        id=_uid(), email="anya@demo.talent", display_name="Аня", region="Москва",
        phone=None, telegram=None, fsp_id=None, specialization="backend",
        declared_grade="middle", assessed_grade=None, experience_years=3,
        salary_from_gross=180_000, salary_to_gross=240_000, is_visible=True, show_city=True,
        show_stack=False, show_fsp=False, show_experience=False, github=None, soft_skills=[],
        category_opened_at=None,
        job_search="active", birth_date=None, minor_consent_given=False,
        guardian_email=None, guardian_consent_at=None, public_profile=False,
        deleted_at=None, discoverable=True, email_verified_at=None,
        fsp_linked_at=None, assessed_at=None, grade_locked_until=None,
        survey_at=None, work_formats=[], skills=[], discipline_scores=[],
        results=[], category=None, profile_version=1, work_goal="job", industry=None,
        token_epoch=0,
    )
    fields.update(extra)
    person = SimpleNamespace(**fields)
    person.minor_now = lambda: False
    return person


def _orm_company() -> Employer:
    return Employer(
        id=_uid(), company_name="Сибирский код", email="hr@sibcode.demo",
        password_hash="x", subscription_tier="free",
    )


def _company(**extra):
    fields = dict(
        id=_uid(), company_name="Сибирский код", email="hr@sibcode.demo", inn=None,
        website=None, description=None, industry=None, subscription_tier="free",
        invites_paused_at=None, deleted_at=None, token_epoch=0,
        totp_secret=None, totp_last_step=None, totp_verified_at=None,
    )
    fields.update(extra)
    return SimpleNamespace(**fields)


def _request(body: bytes = b"{}", headers: list | None = None) -> Request:
    sent = {"done": False}

    async def receive():
        if sent["done"]:
            return {"type": "http.request", "body": b"", "more_body": False}
        sent["done"] = True
        return {"type": "http.request", "body": body, "more_body": False}

    scope = {"type": "http", "method": "POST", "path": "/", "headers": headers or [], "client": ("127.0.0.1", 9)}
    return Request(scope, receive)


@pytest.fixture
def quiet(monkeypatch):
    async def allow(*_args, **_kwargs):
        return False

    async def yes(*_args, **_kwargs):
        return True

    async def nothing(*_args, **_kwargs):
        return None

    for module in (offers, tasks, search, fsp_id_demo, messages, candidates, moderation):
        monkeypatch.setattr(module, "too_many", allow)
    monkeypatch.setattr(offers, "contacts_allowed", yes)
    monkeypatch.setattr("app.services.search.cache.publish_invite", nothing)
    monkeypatch.setattr("app.services.search.cache.bump_bank_epoch", nothing)
    monkeypatch.setattr(legal, "bump_bank_epoch", nothing)
    monkeypatch.setattr(interviews, "bump_bank_epoch", nothing)
    monkeypatch.setattr(candidates, "bump_bank_epoch", nothing)


async def test_error_pages_keep_one_shape():
    app = FastAPI()
    install_error_handlers(app)

    @app.get("/missing")
    def missing():
        raise HTTPException(status_code=404, detail="нет")

    @app.get("/raw")
    def raw():
        raise HTTPException(status_code=422, detail=[{"msg": "поле"}])

    @app.get("/limited")
    def limited():
        raise ApiError(429, "rate_limited", "подождите")

    @app.get("/boom")
    def boom():
        raise RuntimeError("сломалось")

    @app.post("/form")
    def form(n: int):
        return {"n": n}

    client = TestClient(app, raise_server_exceptions=False)
    assert client.get("/missing").json()["error"]["code"]
    body = client.get("/raw").json()
    assert body["error"]["details"] == [{"msg": "поле"}]
    limited_response = client.get("/limited")
    assert limited_response.status_code == 429
    assert limited_response.headers["retry-after"] == "60"
    assert client.get("/boom").status_code == 500
    invalid = client.post("/form", json={"n": "нет"})
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "validation_error"

    from app.core.body_limit import LimitRequestBody

    capped = FastAPI()

    @capped.post("/echo")
    async def echo(request: Request):
        return {"n": len(await request.body())}

    capped.add_middleware(LimitRequestBody, max_bytes=8)
    capped_client = TestClient(capped)
    too_big = capped_client.post("/echo", content=b"123456789")
    assert too_big.status_code == 413
    assert too_big.json()["error"]["code"] == "payload_too_large"
    assert capped_client.post("/echo", content=b"1234").json()["n"] == 4

    streamed = []

    async def receive_stream():
        return {"type": "http.request", "body": b"12345", "more_body": False}

    async def send_stream(message):
        streamed.append(message)

    async def untouched(scope, receive, send):
        raise AssertionError("oversized stream must not reach the route")

    await LimitRequestBody(untouched, max_bytes=4)(
        {"type": "http", "method": "POST", "headers": []}, receive_stream, send_stream)
    assert streamed[0]["status"] == 413


async def test_token_opens_the_account_and_a_closed_one_does_not():
    subject = _uid()
    account = SimpleNamespace(token_epoch=0, deleted_at=None)
    db = Bag()
    db.gets = [account, account, account]
    token = create_access_token(str(subject), "participant")
    opened = await get_current_participant(token, db)
    assert opened["sub"] == str(subject)
    assert (await get_any_auth(token, db))["role"] == "participant"
    employer_token = create_access_token(str(subject), "employer")
    assert (await get_current_employer(employer_token, db))["role"] == "employer"

    closed = Bag()
    closed.gets = [SimpleNamespace(token_epoch=0, deleted_at=NOW)]
    with pytest.raises(HTTPException) as denied:
        await get_current_participant(token, closed)
    assert denied.value.status_code == 401

    stale = Bag()
    stale.gets = [SimpleNamespace(token_epoch=2, deleted_at=None)]
    with pytest.raises(HTTPException):
        await get_current_participant(token, stale)
    with pytest.raises(HTTPException):
        await get_current_participant("not-a-token", Bag())
    foreign = create_token({"sub": "не-uuid", "role": "participant", "type": "access"}, 5)
    with pytest.raises(HTTPException):
        await get_any_auth(foreign, Bag())


async def test_bell_lists_and_marks_one_row(quiet):
    me = _uid()
    current = _current("participant", me)
    row = SimpleNamespace(
        id=_uid(), kind="offer_new", title="Приглашение", body="есть", link="/candidate/offers",
        created_at=NOW, read_at=None, recipient_role="participant", recipient_id=me,
    )
    db = Bag()
    db.scalars_q = [[row]]
    db.scalar_q = [1]
    listed = await notifications.list_notifications(15, current, db)
    assert listed["unread"] == 1 and listed["items"][0]["read"] is False

    db.gets = [row]
    marked = await notifications.mark_read(row.id, current, db)
    assert marked["read"] is True and db.commits == 1

    db.execute_q = [Exec(rowcount=3)]
    assert (await notifications.mark_all_read(current, db))["marked"] == 3
    with pytest.raises(ApiError):
        notifications._me({"role": "guest", "sub": str(me)})


async def test_favorites_keep_only_people_still_in_search(monkeypatch):
    company = _company()
    current = _current("employer", company.id)
    kept, gone = _uid(), _uid()

    async def cards(db, ordered, *rest, **_extra):
        return [{"candidate_id": str(pid), "why": []} for pid in ordered]

    monkeypatch.setattr(favorites, "_build_cards", cards)
    db = Bag()
    db.scalars_q = [[kept]]
    db.scalar_q = [None, 0]
    added = await favorites.add_favorite(kept, current, db)
    assert added["favorite"] and db.added[-1].participant_id == kept and db.commits == 1

    db.scalars_q = [[kept]]
    db.scalar_q = [_uid()]
    await favorites.add_favorite(kept, current, db)
    assert len(db.added) == 1 and db.commits == 1

    db.scalars_q = [[]]
    with pytest.raises(ApiError) as hidden:
        await favorites.add_favorite(gone, current, db)
    assert hidden.value.status_code == 404

    extra = _uid()
    db.scalars_q = [[extra]]
    db.scalar_q = [None, favorites.FAVORITES_MAX]
    with pytest.raises(ApiError) as full:
        await favorites.add_favorite(extra, current, db)
    assert full.value.status_code == 409

    rows = [SimpleNamespace(participant_id=gone, created_at=NOW, interest="saved"),
            SimpleNamespace(participant_id=kept, created_at=NOW, interest="saved")]
    db.scalars_q = [rows, [kept]]
    listed = await favorites.list_favorites(current, db)
    assert listed["ids"] == [str(kept)] and listed["hidden"] == 1
    assert listed["items"][0]["saved_at"] == NOW.isoformat()

    removed = await favorites.remove_favorite(kept, current, db)
    assert removed["favorite"] is False


async def test_moderation_desk_lists_and_closes(quiet, monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MODE", True)
    company = _company()
    current = _current("employer", company.id)
    when = NOW
    complaint = SimpleNamespace(id=_uid(), reason="не_вакансия", vacancy_id=_uid(), offer_id=None, created_at=when)
    db = Bag()
    db.gets = [company]
    db.scalars_q = [[complaint]]
    rows = await moderation.complaints(current, db)
    assert rows[0]["reason"] == "fake"

    vacancy = SimpleNamespace(id=_uid(), is_open=True)
    db.gets = [company, vacancy]
    closed = await moderation.close_vacancy(vacancy.id, current, db)
    assert closed["is_open"] is False

    stranger = _company(email="other@demo.talent")
    db.gets = [stranger]
    with pytest.raises(ApiError) as hidden:
        await moderation.complaints(current, db)
    assert hidden.value.status_code == 404

    from app.services.ai import drafts, providers

    async def agree(model, system, user):
        return '{"stem": "Сколько раз выполнится цикл?", "key": "6"}' if model == "writer" else '{"key": "6"}'

    monkeypatch.setattr(drafts, "_chat", agree)
    for name, value in (("AI_ENABLED", True), ("GIGACHAT_CREDENTIALS", "present"),
                        ("GIGACHAT_MODEL", "writer"), ("GIGACHAT_CHECK_MODEL", "checker")):
        monkeypatch.setattr(providers.settings, name, value)
    db = Bag()
    db.gets = [company]
    with pytest.raises(ApiError) as wrong:
        await moderation.request_draft(moderation.DraftIn(spec="backend", topic="ui", level=2), current, db)
    assert wrong.value.status_code == 422
    db.gets = [company]
    made = await moderation.request_draft(moderation.DraftIn(spec="backend", topic="python", level=2), current, db)
    assert made["accepted"] and made["draft"]["status"] == "pending" and made["draft"]["key"] == "6"
    draft = db.added[-1]

    db.gets = [company, draft]
    done = await moderation.review_draft(draft.id, moderation.ReviewIn(decision="approved", note="в семейство циклов"),
                                         current, db)
    assert done["status"] == "approved" and done["reviewed_at"]
    db.gets = [company, draft]
    with pytest.raises(ApiError) as twice:
        await moderation.review_draft(draft.id, moderation.ReviewIn(decision="rejected"), current, db)
    assert twice.value.status_code == 409

    async def disagree(model, system, user):
        return '{"stem": "Сколько раз?", "key": "6"}' if model == "writer" else '{"key": "7"}'

    monkeypatch.setattr(drafts, "_chat", disagree)
    db = Bag()
    db.gets = [company]
    lost = await moderation.request_draft(moderation.DraftIn(spec="backend", topic="python", level=2), current, db)
    assert lost == {"accepted": False, "reason": "disagree", "draft": None} and not db.added

    monkeypatch.setattr(providers.settings, "GIGACHAT_CHECK_MODEL", "")
    db.gets = [company]
    listed_off = await moderation.item_drafts("pending", current, db)
    assert listed_off["model_ready"] is False
    db.gets = [company]
    with pytest.raises(ApiError) as off:
        await moderation.request_draft(moderation.DraftIn(spec="backend", topic="python", level=2), current, db)
    assert off.value.status_code == 503


async def test_employer_profile_round_trip(quiet):
    company = _company()
    current = _current("employer", company.id)
    db = Bag()
    db.gets = [company]
    card = await employer.get_me(current, db)
    assert card.company_name == "Сибирский код"

    db.gets = [company]
    updated = await employer.update_me(
        employer.EmployerProfileUpdate(company_name="Новое имя", inn="7707083893", industry="финтех"),
        current, db)
    assert updated.company_name == "Новое имя" and company.inn == "7707083893"

    db.gets = [company]
    with pytest.raises(HTTPException) as bad:
        await employer.update_me(employer.EmployerProfileUpdate(inn="7707083894"), current, db)
    assert bad.value.status_code == 422


async def test_legal_documents_and_consent_withdrawal(quiet, monkeypatch):
    listed = await legal.list_documents("participant")
    assert listed and all(row["sha256"] for row in listed)
    one = await legal.read_document(listed[0]["kind"])
    assert "body_md" in one
    with pytest.raises(ApiError):
        await legal.read_document("нет-такого")

    me = _uid()
    current = _current("participant", me)
    consent = SimpleNamespace(kind=listed[0]["kind"], version="1", sha256="другой", withdrawn_at=None, given_at=NOW)
    db = Bag()
    db.scalars_q = [[consent]]
    mine = await legal.my_consents(current, db)
    assert any(row["outdated"] for row in mine)

    saved = SimpleNamespace(kind="pd_candidate", version="1.2", given_at=NOW)

    async def give(*_args, **_kwargs):
        return saved

    async def withdraw(*_args, **_kwargs):
        return saved

    monkeypatch.setattr(legal, "give_consent", give)
    monkeypatch.setattr(legal, "withdraw_consent", withdraw)
    given = await legal.give(legal.ConsentIn(kind="pd_candidate"), _request(), current, Bag())
    assert given["kind"] == "pd_candidate"

    person = _person(id=me, public_profile=True, is_visible=True)
    db.gets = [person]
    effect = await legal.withdraw("pd_candidate", _request(), current, db)
    assert effect["withdrawn"] is True and person.is_visible is False


async def test_demo_fsp_login_returns_a_code(quiet, monkeypatch):
    monkeypatch.setattr(settings, "FSP_ID_MODE", "mock")

    async def issue(*_args, **_kwargs):
        return "one-time"

    monkeypatch.setattr(MockFspIdProvider, "issue_code", issue)
    body = fsp_id_demo.DemoLoginIn(
        fsp_id="fsp2000", password="test", client_id="fsp-talent", redirect_uri="http://localhost/cb",
        state="state-state", code_challenge="a" * 43, code_challenge_method="S256",
    )
    out = await fsp_id_demo.demo_login(body)
    assert "code=one-time" in out["redirect_to"] and "state=state-state" in out["redirect_to"]

    wrong = body.model_copy(update={"password": "нет"})
    with pytest.raises(ApiError) as bad:
        await fsp_id_demo.demo_login(wrong)
    assert bad.value.status_code == 400


async def test_parse_endpoints_return_a_reading(quiet):
    resume = await ai.parse_resume_endpoint(ai.ResumeIn(text="Пишу сервисы на Python и FastAPI"), {"sub": str(_uid())})
    assert any(item["name"] == "Python" for item in resume["skills"])
    query = await ai.parse_query_endpoint(ai.QueryIn(q="сеньор бэкенд python"), {"sub": str(_uid())})
    assert query["role"] or query["grade"] or query["skills"] is not None


async def test_search_bank_and_filters(quiet, monkeypatch):
    async def grid(_db):
        return {"rows": []}

    async def found(*_args, **_kwargs):
        return {"items": [{"id": "1"}]}

    monkeypatch.setattr(search, "bank_grid", grid)
    monkeypatch.setattr(search, "search_candidates", found)
    current = _current("employer")
    assert await search.bank(current, Bag()) == {"rows": []}
    page = await search.search(
        q="Python", role="backend", grade="middle", discipline=None, min_rank=None, skills="FastAPI, нет",
        limit=5, fresh_days=None, assessed_only=False, has_fsp=None, work_goal=None, city="Москва",
        work_format="remote", industry=None, current=current, db=Bag(),
    )
    assert page["items"]
    with pytest.raises(ApiError):
        await search.search(
            q=None, role=None, grade=None, discipline=None, min_rank=None, skills=None, limit=5,
            fresh_days=None, assessed_only=False, has_fsp=None, work_goal=None, city="Нет такого города",
            work_format=None, industry=None, current=current, db=Bag(),
        )


def _offer(employer_id, candidate_id, **extra):
    fields = dict(
        id=_uid(), employer_id=employer_id, candidate_id=candidate_id, role="Backend",
        salary_from_gross=150_000, salary_to_gross=200_000, currency="RUB", work_format="remote",
        message=None, status="pending", created_at=NOW, expires_at=NOW, contact_method="почта",
        candidate_viewed_at=None, contacts_revoked_at=None, contacts_revealed_at=None,
        decline_reason=None, perks=[], practice_stage=None,
    )
    fields.update(extra)
    return SimpleNamespace(**fields)


async def test_offer_preview_market_list_and_withdraw(quiet):
    company = _company()
    person = _person()
    current = _current("employer", company.id)
    db = Bag()
    db.gets = [company, person]
    hint = await offers.preview_offer(
        offers.SalaryPreview(candidate_id=person.id, salary_to_gross=200_000), current, db)
    assert "salary_hint" in hint

    db.gets = [company]
    db.scalars_q = [["salary"]]
    db.execute_q = [Exec([("backend", "middle", 180_000)] * 5)]
    market = await offers.offer_market(current, db)
    assert market["salaries"]

    pending = _offer(company.id, person.id)
    db.scalars_q = [[pending], []]
    listed = await offers.list_my_offers(current, db)
    assert listed[0]["candidate"]["label"] == "Кандидат"

    pending.status = "pending"
    db.gets = [pending, company]
    assert (await offers.withdraw_offer(pending.id, current, db))["status"] == "withdrawn"


async def test_offer_create_and_contact_reveal(quiet):
    company = _company()
    person = _person()
    current = _current("employer", company.id)
    db = Bag()
    db.gets = [company, person]
    db.scalar_q = [None]
    db.scalars_q = [[]]
    body = offers.OfferCreate(
        candidate_id=person.id, salary_from_gross=150_000, salary_to_gross=200_000,
        role="Backend", contact_method="почта",
    )
    created = await offers._create_offer(body, current, db)
    assert created["status"] == "pending" and "salary_hint" in created

    accepted = _offer(company.id, person.id, status="accepted")
    db.gets = [accepted, person]
    revealed = await offers.reveal_contacts(accepted.id, current, db)
    assert revealed["email"] == person.email


async def test_create_offer_replays_a_stored_body(quiet, monkeypatch):
    async def replay(*_args, **_kwargs):
        return {"status": 201, "body": {"status": "pending", "id": "stored"}}

    monkeypatch.setattr(offers, "idem_begin", replay)
    body = offers.OfferCreate(
        candidate_id=_uid(), salary_from_gross=100_000, salary_to_gross=120_000,
        role="Backend", contact_method="почта",
    )
    response = await offers.create_offer(body, _current("employer"), Bag(), idempotency_key="same-key")
    assert response.status_code == 201
    assert json.loads(response.body)["id"] == "stored"


async def test_messages_open_after_accept(quiet):
    company = _company()
    person = _person()
    offer = _offer(company.id, person.id, status="accepted")
    current = _current("participant", person.id)
    posted_at = NOW
    note = SimpleNamespace(id=_uid(), author_role="employer", body="Добрый день", created_at=posted_at, read_at=None)
    db = Bag()
    db.gets = [offer]
    db.scalars_q = [[note]]
    thread = await messages.list_messages(offer.id, current, db)
    assert thread["can_post"] is True and thread["messages"][0]["mine"] is False

    db.gets = [offer]
    db.scalar_q = [company.company_name]
    sent = await messages.post_message(offer.id, messages.MessageIn(body="  Ответ  "), current, db)
    assert sent["body"] == "Ответ" and sent["mine"] is True
    counts = await messages.unread_counts(Bag(), [], "participant")
    assert counts == {}


async def test_interview_slots_choice_and_outcome(quiet):
    company = _company()
    person = _person()
    offer = _offer(company.id, person.id, status="accepted")
    employer_current = _current("employer", company.id)
    candidate_current = _current("participant", person.id)
    fresh = SimpleNamespace(
        id=_uid(), starts_at=datetime(2027, 6, 1, 7, tzinfo=UTC), format="online", place=None,
        chosen=False, outcome=None,
    )
    db = Bag()
    db.gets = [offer, company]
    db.scalars_q = [[], [fresh]]
    proposed = await interviews.propose_slots(
        offer.id, interviews.SlotsIn(slots=[interviews.SlotIn(date="2027-06-01", time="10:00", format="online")]),
        employer_current, db)
    assert proposed["slots"]

    chosen = SimpleNamespace(
        id=fresh.id, starts_at=fresh.starts_at, format="online", place=None, chosen=False, outcome=None,
    )
    db.gets = [offer, person]
    db.scalars_q = [[chosen], [chosen]]
    picked = await interviews.choose_slot(offer.id, chosen.id, candidate_current, db)
    assert picked["slots"][0]["chosen"] is True

    chosen.chosen = True
    db.gets = [offer, company]
    db.scalars_q = [[chosen]]
    calendar = await interviews.download_calendar(offer.id, candidate_current, db)
    assert calendar.media_type == "text/calendar"

    db.gets = [offer]
    db.scalars_q = [[chosen]]
    outcome = await interviews.set_outcome(
        offer.id, interviews.OutcomeIn(outcome="passed"), employer_current, db)
    assert outcome["outcome"] == "passed"


async def test_need_versions(quiet):
    with pytest.raises(ValidationError):
        needs.NeedParams(role="нет", salary_from=10, salary_to=1)
    params = needs.NeedParams(role="backend", grade="middle", skills=["fastapi"], salary_from=100, salary_to=200)
    assert params.spec().role == "backend"
    owner = _uid()
    current = _current("employer", owner)
    db = Bag()
    created = await needs.create_need(needs.NeedIn(title="Платежи", params=params), current, db)
    assert created["version"] == 1

    need = db.added[0]
    ver = db.added[1]
    db.scalars_q = [[need]]
    db.execute_q = [Exec([(need.id, 2)])]
    db.scalars_q.append([ver])
    listed = await needs.list_needs(current, db)
    assert listed[0]["shortlist_count"] == 2

    db.gets = [need]
    db.scalar_q = [ver]
    restored = await needs.restore_need(need.id, 1, current, db)
    assert restored["version"] == 2
    bag = Bag()
    bag.gets = [need]
    assert (await needs.archive_need(need.id, current, bag))["archived"] is True


async def test_vacancy_write_exam_and_apply(quiet):
    company = _orm_company()
    current = _current("employer", company.id)
    body = vacancies.VacancyIn(
        title="Бэкенд", description="API", role="backend", grade="junior", skills=["Python"],
        salary_from_gross=150_000, salary_to_gross=200_000,
    )
    db = Bag()
    db.gets = [company]
    created = await vacancies.create_vacancy(body, current, db)
    assert created["title"] == "Бэкенд"
    vacancy = db.added[0]
    vacancy.employer = company
    db.gets = [vacancy, company]
    changed = await vacancies.update_vacancy(vacancy.id, body, current, db)
    assert changed["company"] == company.company_name

    db.gets = [company]
    exam = await vacancies.preview_exam(body, current, db)
    assert isinstance(exam, dict) and exam

    application = SimpleNamespace(status="applied", candidate_id=_uid())
    db.gets = [vacancy, company]
    db.scalars_q = [[application]]
    assert (await vacancies.close_vacancy(vacancy.id, current, db))["is_open"] is False

    person = _person()
    category = SimpleNamespace(primary_role="backend", grade="middle")
    score = SimpleNamespace(discipline="algorithmic", best_rank=None)
    open_vacancy = SimpleNamespace(
        id=_uid(), employer_id=company.id, employer=company, title="Бэкенд", role="backend", grade="junior",
        grade_match="plus_minus",
        discipline=None, min_rank=None, skills=["Python"], allows_minors=True, is_open=True,
        salary_from_gross=150_000, salary_to_gross=200_000, work_format="remote", description="API",
    )
    me = _current("participant", person.id)
    db.gets = [person]
    db.scalar_q = [category]
    db.scalars_q = [["Python"], [score], [], [open_vacancy]]
    cards = await vacancies.vacancies_for_me(me, db)
    assert isinstance(cards, list)

    db.gets = [person, open_vacancy]
    db.scalar_q = [category]
    db.scalars_q = [["Python"], [score]]
    applied = await vacancies.apply(open_vacancy.id, me, db)
    assert applied["status"] == "applied"


async def test_task_create_list_and_review(quiet):
    company = _company()
    current = _current("employer", company.id)
    body = tasks.TaskCreate(
        title="Сумма списка", statement="Сложите положительные числа списка и верните сумму.",
        answer_type="number", reference_number="6", visibility="public", specialization="backend",
    )
    db = Bag()
    db.gets = [company]
    created = await tasks.create_task(body, current, db)
    assert created["title"] == "Сумма списка"
    catalog = await tasks.lab_catalog(current)
    assert catalog
    task = db.added[0]
    db.scalars_q = [[task]]
    db.execute_q = [Exec([(task.id, 1, 1, 0)])]
    mine = await tasks.my_tasks(current, db)
    assert mine[0]["submissions"] == 1

    submission = SimpleNamespace(
        id=_uid(), task_id=task.id, participant_id=_uid(), status="review", passed=None, comment=None,
        answer_text="6", answer_index=None, submitted_at=NOW, reviewed_at=None,
    )
    db.gets = [task]
    db.scalars_q = [[submission], []]
    packed = await tasks.task_submissions(task.id, current, db)
    assert packed["submissions"][0]["candidate_id"]

    person = _person(id=submission.participant_id)
    db.gets = [submission, task, person, company]
    reviewed = await tasks.review_submission(
        submission.id, tasks.ReviewIn(passed=True, comment="верно"), current, db)
    assert reviewed["passed"] is True
    bag = Bag()
    bag.gets = [task]
    closed = await tasks.close_task(task.id, current, bag)
    assert closed["is_open"] is False


async def test_candidate_profile_market_and_growth(quiet):
    person = _person()
    person.minor_now = lambda: False
    current = _current("participant", person.id)
    db = Bag()
    db.scalar_q = [person]
    db.scalars_q = [[]]
    profile = await candidates.get_my_profile(current, db)
    assert profile["display_name"] == "Аня" and profile["discoverable"] is True
    assert profile["completeness"]["total"] == 8
    assert "skills" in profile["completeness"]["missing"]
    assert "city" not in profile["completeness"]["missing"]

    category = SimpleNamespace(primary_role="backend", grade="middle")
    db.gets = [person]
    db.scalar_q = [category]
    db.scalars_q = [[180_000, 200_000, 220_000, 240_000, 260_000]]
    market = await candidates.my_salary_market(current, db)
    assert market["cell"] is not None

    db.gets = [person]
    db.scalar_q = [category, 6]
    db.execute_q = [Exec([("PostgreSQL", 6)])]
    db.scalars_q = [[], [180_000, 200_000, 220_000, 240_000, 260_000]]
    growth = await candidates.my_growth(current, db)
    assert growth["next_grade"] == "senior"

    db.gets = [person]
    visible = await candidates.update_visibility(candidates.VisibilityUpdate(is_visible=False), current, db)
    assert visible["is_visible"] is False

    result = SimpleNamespace(
        id=_uid(), event_name="Кубок", discipline="algorithmic", competition_status="completed",
        place=2, total_participants=40, is_team=False, team_size=1, event_date=NOW,
        protocol_url=None, trust_level="official", raw_data={"ekp_number": "ЕКП-демо-1"},
    )
    db.scalars_q = [[result]]
    rows = await candidates.get_my_results(50, 0, current, db)
    assert rows[0]["place"] == 2


async def test_public_profile_credential_and_pdf(quiet):
    person = _person(public_profile=True, display_name="Аня")
    skill = SimpleNamespace(
        name="Python", trust_level="test_confirmed", confirmed=True, created_at=NOW, confirmed_at=NOW)
    score = SimpleNamespace(
        discipline="algorithmic", score=1.2, lcb=0.8, confidence=0.9, best_rank="1 юношеский",
        rank_assigned_at=NOW, rank_order_ref=None, events_count=3,
    )
    person.skills = [skill]
    person.discipline_scores = [score]
    person.category = SimpleNamespace(
        primary_role="backend", grade="middle", grade_source="test", stack=["Python"], explanation=["тест"],
    )
    db = Bag()
    db.scalar_q = [person]
    card = await public.get_public_profile(person.id, db)
    assert card["display_name"] == "Аня" and card["skills"]

    db.scalar_q = [person]
    pdf = await public.public_profile_pdf(person.id, db)
    assert pdf.media_type == "application/pdf"

    credential = SimpleNamespace(id=_uid(), participant_id=person.id, credential_json={"id": "urn:uuid:" + str(_uid())},
                                 revoked_at=None, issued_at=NOW)
    db.gets = [credential]
    db.scalar_q = [person.id]
    checked = await public.verify_stored(credential.id, db)
    assert checked["signature"] is False or "valid" in checked

    db.scalar_q = [person.id]
    db.scalars_q = [[credential]]
    listed = await public.get_credentials(person.id, db)
    assert listed[0]["id"]

    db.gets = [credential]
    status = await public.credential_status(credential.id, db)
    assert status["revoked"] is False

    posted = await public.verify_posted(_request(b'{"id": "not-a-uuid"}'), Bag())
    assert posted["signature"] is False
    with pytest.raises(HTTPException) as huge:
        await public.verify_posted(_request(b"{" + b" " * 70_000), Bag())
    assert huge.value.status_code == 413
    assert await public.demo_stand() == {
        "demo_mode": bool(settings.DEMO_MODE),
        "mail_console": bool(settings.DEMO_MODE and settings.MAIL_MODE == "console"),
    }


async def test_data_export_for_both_roles(quiet):
    person = _person()
    current = _current("participant", person.id)
    db = Bag()
    db.gets = [person]
    db.scalar_q = [None]
    exported = await auth.export_my_data(current, db)
    assert exported.headers["content-disposition"].startswith("attachment")
    assert b"participant" in exported.body

    company = _company()
    db.gets = [company]
    company_file = await auth.export_my_data(_current("employer", company.id), db)
    assert b"employer" in company_file.body
    assert await auth.whoami(current) == {"sub": current["sub"], "role": "participant"}


async def test_tab_leave_dispute_and_review(quiet, monkeypatch):
    person_id = _uid()
    current = _current("participant", person_id)
    session = SimpleNamespace(
        id=_uid(), participant_id=person_id, engine="cat_v2", status="in_progress", flags={},
        specialization="backend", target_grade="middle", expires_at=NOW, p_pass=0.4,
        irt_theta=0.1, theta_se=0.3,
    )
    db = Bag()
    db.gets = [session]
    left = await assessment.leave_tab(session.id, current, db)
    assert left["tab_leaves"] == 1
    db.gets = [session]
    copied = await assessment.copy_stem(session.id, current, db)
    assert copied["copies"] == 1
    notes = assessment._review_notes(session.flags)
    assert any("копировали" in line for line in notes)
    assert any("Грейд не изменён" in line for line in notes)

    session.status = "completed"
    db.gets = [session]
    db.scalar_q = [None]
    disputed = await assessment.dispute_grade(session.id, current, db)
    assert "Грейд этой кнопкой не меняется" in disputed["text"]

    item = SimpleNamespace(
        kind="code", seq=1, topic="python", family_id="py_eval", level=2, stem="вопрос", code="x",
        language="python", typed=True, options=["6"], answer_index=None, answer_text="6",
        is_correct=True, timed_out=False, excluded=False, correct_index=0, explanation="сумма",
        answered_at=NOW,
    )

    async def items(_db, _sid):
        return [item]

    monkeypatch.setattr(assessment, "session_items", items)
    session.status = "completed"
    db.gets = [session]
    review = await assessment.review(session.id, current, db)
    assert review["items"][0]["right_text"] == "6"

    async def stopped(_db, _sid, _pid):
        session.status = "abandoned"
        return session

    monkeypatch.setattr(assessment, "abandon", stopped)
    abandoned = await assessment.abandon_session(session.id, current, db)
    assert abandoned.status == "abandoned"
