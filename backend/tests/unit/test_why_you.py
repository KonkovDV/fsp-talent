"""«Почему вас пригласили»: the candidate sees which of their own signals led the employer to them."""
import json
import uuid
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

from app.api.v1 import candidates
from app.services.offer_why import MAX_LINES, offer_role, why_invited

NOW = datetime(2026, 10, 9, 12, tzinfo=UTC)
CONTACT_KEYS = {"email", "phone", "telegram", "display_name", "fsp_id", "birth_date"}


def _codes(lines):
    return [line["code"] for line in lines]


def test_assessed_candidate_with_fsp_history_gets_the_three_confirmed_reasons():
    lines = why_invited(offer_title="Backend-разработчик", offer_format="remote", role="backend", grade="middle",
                        grade_source="assessed", assessed_at=date(2026, 10, 3),
                        fsp_scores={"algorithmic": 0.71}, work_formats=["remote", "hybrid"])
    assert _codes(lines) == ["CATEGORY_MATCH", "GRADE_ASSESSED", "FSP_RELEVANT", "FORMAT_MATCH"]
    assert "03.10.2026" in lines[1]["text"]
    assert "Алгоритмическое программирование" in lines[2]["text"]


def test_candidate_without_fsp_is_told_the_axis_does_not_penalise():
    lines = why_invited(offer_title="Python backend developer", offer_format="office", role="backend",
                        grade="junior", grade_source="declared", assessed_at=None, fsp_scores={},
                        work_formats=[])
    assert _codes(lines) == ["CATEGORY_MATCH", "GRADE_DECLARED", "FSP_NEUTRAL"]
    assert "не снижает" in lines[2]["text"]
    assert "ниже" in lines[1]["text"]


def test_other_discipline_and_other_role_and_other_format():
    lines = why_invited(offer_title="Аналитик данных", offer_format="office", role="backend", grade="middle",
                        grade_source="assessed", assessed_at=None, fsp_scores={"robotics": 0.6},
                        work_formats=["remote"])
    assert _codes(lines) == ["CATEGORY_OTHER", "GRADE_ASSESSED", "FSP_OTHER", "FORMAT_OTHER"]
    assert "0,5" in lines[2]["text"]
    assert lines[1]["text"].endswith("тестом")


def test_role_without_profile_discipline_reads_the_plain_fsp_line():
    lines = why_invited(offer_title="QA-инженер", offer_format="remote", role="qa", grade="junior",
                        grade_source="assessed", assessed_at=None, fsp_scores={"product": 0.4},
                        work_formats=None)
    assert _codes(lines) == ["CATEGORY_MATCH", "GRADE_ASSESSED", "FSP_SCORE"]


def test_no_category_still_explains_fsp_and_format():
    lines = why_invited(offer_title="Стажёр", offer_format="remote", role=None, grade=None, grade_source=None,
                        assessed_at=None, fsp_scores={}, work_formats=["remote"])
    assert _codes(lines) == ["FSP_NEUTRAL", "FORMAT_MATCH"]


def test_at_most_four_lines_and_each_has_code_and_text():
    lines = why_invited(offer_title="Fullstack", offer_format="hybrid", role="fullstack", grade="senior",
                        grade_source="assessed", assessed_at=NOW, fsp_scores={"product": 0.9},
                        work_formats=["hybrid"])
    assert len(lines) <= MAX_LINES
    assert all(set(line) == {"code", "text"} and line["text"] for line in lines)


def test_offer_role_reads_free_text_titles():
    assert offer_role("Backend-разработчик") == "backend"
    assert offer_role("Бэкенд-разработчик Go") == "backend"
    assert offer_role("Fullstack (React + Python)") == "fullstack"
    assert offer_role("Frontend-разработчик") == "frontend"
    assert offer_role("ML-инженер") == "ml"
    assert offer_role("Инженер данных") == "data"
    assert offer_role("Специалист по ИБ") == "security"
    assert offer_role("QA automation") == "qa"
    assert offer_role("Стажёр") is None
    assert offer_role("Mlops") is None  # short words match whole words only
    assert offer_role(None) is None


# --- the route: why_you is in every offer and holds no contact or employer-side data ---------------------

class _Rows:
    def __init__(self, rows):
        self._rows = list(rows)

    def __iter__(self):
        return iter(self._rows)

    def all(self):
        return list(self._rows)


class _Db:
    def __init__(self, offers, cat, me, scores):
        self.scalars_q = [offers, []]
        self.scalar_q = [cat]
        self.gets = [me]
        self.execute_q = [scores]
        self.commits = 0

    async def scalars(self, stmt):
        return _Rows(self.scalars_q.pop(0) if self.scalars_q else [])

    async def scalar(self, stmt):
        return self.scalar_q.pop(0) if self.scalar_q else None

    async def get(self, model, ident=None, **kwargs):
        return self.gets.pop(0) if self.gets else None

    async def execute(self, stmt):
        return _Rows(self.execute_q.pop(0) if self.execute_q else [])

    async def commit(self):
        self.commits += 1


def _route_deps(monkeypatch):
    async def none(*_a, **_k):
        return None

    async def empty(*_a, **_k):
        return {}

    monkeypatch.setattr(candidates, "unread_counts", empty)
    monkeypatch.setattr(candidates, "role_median", none)
    monkeypatch.setattr(candidates, "company_reputation", empty)


def _employer():
    return SimpleNamespace(id=uuid.uuid4(), company_name="Сибирский код", industry="Финтех", website=None,
                           description=None, inn=None, verified_at=None, suspended_at=None, email_verified_at=None,
                           created_at=NOW, inn_verified_at=None, domain_verified_at=None)


def _offer(employer, **extra):
    fields = dict(id=uuid.uuid4(), employer_id=employer.id, employer=employer, role="Backend-разработчик",
                  salary_from_gross=180_000, salary_to_gross=240_000, currency="RUB", work_format="remote",
                  message=None, perks=[], practice_stage=None, contact_method="почта", status="pending",
                  created_at=NOW, expires_at=datetime.now(UTC) + timedelta(days=7),
                  candidate_viewed_at=NOW, contacts_revoked_at=None)
    fields.update(extra)
    return SimpleNamespace(**fields)


async def test_my_offers_why_you_for_assessed_candidate_with_fsp(monkeypatch):
    _route_deps(monkeypatch)
    pid = uuid.uuid4()
    employer = _employer()
    cat = SimpleNamespace(primary_role="backend", grade="middle", grade_source="assessed")
    me = SimpleNamespace(id=pid, assessed_at=datetime(2026, 10, 3, tzinfo=UTC), work_formats=["remote"],
                         email="anya@demo.talent", phone="+79990000000", telegram="@anya")
    db = _Db([_offer(employer)], cat, me, [("algorithmic", 0.7)])
    listed = await candidates.get_my_offers(limit=50, offset=0, current={"sub": str(pid), "role": "participant"},
                                            db=db)
    why = listed[0]["why_you"]
    assert {"CATEGORY_MATCH", "GRADE_ASSESSED", "FSP_RELEVANT"} <= set(_codes(why))
    dumped = json.dumps(listed, ensure_ascii=False)
    assert not CONTACT_KEYS & set(listed[0])
    assert "anya@demo.talent" not in dumped and "+79990000000" not in dumped and "@anya" not in dumped


async def test_my_offers_why_you_for_candidate_without_fsp(monkeypatch):
    _route_deps(monkeypatch)
    pid = uuid.uuid4()
    employer = _employer()
    cat = SimpleNamespace(primary_role="backend", grade="junior", grade_source="declared")
    me = SimpleNamespace(id=pid, assessed_at=None, work_formats=[])
    db = _Db([_offer(employer)], cat, me, [])
    listed = await candidates.get_my_offers(limit=50, offset=0, current={"sub": str(pid), "role": "participant"},
                                            db=db)
    assert "FSP_NEUTRAL" in _codes(listed[0]["why_you"])
    assert "GRADE_DECLARED" in _codes(listed[0]["why_you"])
