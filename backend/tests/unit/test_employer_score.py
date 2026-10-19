"""The company figure is a labelled demo score and stays inside 0..10."""
import pytest

from app.core.config import settings
from app.services.employer_rating import EmployerTrustSignals, compute_trust_score
from app.services.employer_score import company_score

pytestmark = pytest.mark.usefixtures("_demo_company_scores")


@pytest.fixture
def _demo_company_scores(monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MODE", True)


def test_the_open_signals_stay_on_a_zero_to_ten_scale():
    mid = compute_trust_score(EmployerTrustSignals("", True, 2, 4.0, 5.0))
    assert mid == 6.1
    floor = compute_trust_score(EmployerTrustSignals("", False, 0, 1.0, 10.0))
    assert floor == 0.0
    cap = compute_trust_score(EmployerTrustSignals("7700000000", True, 100, 5.0, 0.0))
    assert cap == 8.5


def test_a_known_name_is_stable_and_labelled_as_demo():
    first = company_score("Сибирский код")
    assert first == company_score("Сибирский код")
    assert first["demo"] is True and 0 <= first["score"] <= 10
    assert first["label"] in ("низкий", "средний", "высокий")
    assert "tier" not in first


def test_an_unknown_name_does_not_leave_the_scale():
    row = company_score("Несуществующая контора 42")
    assert 0 <= row["score"] <= 10 and row["demo"] is True


def test_a_live_stand_does_not_invent_a_company_score(monkeypatch):
    monkeypatch.setattr(settings, "DEMO_MODE", False)
    row = company_score("Несуществующая контора 42")
    assert row["score"] is None and row["demo"] is False
    assert "не показывается" in row["note"]
