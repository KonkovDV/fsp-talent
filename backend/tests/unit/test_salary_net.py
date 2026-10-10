import pytest
from pydantic import ValidationError

from app.api.v1.offers import OfferCreate
from app.api.v1.vacancies import VacancyIn
from app.services.salary_net import annual_tax, as_gross, gross_for_net, net_monthly


def test_scale_edges():
    assert annual_tax(2_400_000) == 312_000
    assert annual_tax(2_400_000 + 100) == 312_000 + 15
    assert net_monthly(200_000) == 174_000
    # 300 000 a month crosses into the 15% band.
    assert net_monthly(300_000) == 259_000


def test_round_trip_stays_within_a_hundred():
    for net in (100_000, 174_000, 250_000, 400_000):
        back = net_monthly(gross_for_net(net))
        assert 0 <= back - net <= 100


def test_an_invite_typed_take_home_is_stored_before_tax():
    gross = as_gross(174_000, "net")
    offer = OfferCreate(
        candidate_id="00000000-0000-0000-0000-000000000001", role="Backend",
        salary_from_gross=174_000, salary_to_gross=174_000, salary_basis="net",
        contact_method="почта hr@example.ru")
    assert offer.salary_from_gross == gross
    assert as_gross(180_000, "gross") == 180_000


def test_a_ruble_fork_and_a_link_are_refused():
    with pytest.raises(ValidationError):
        OfferCreate(
            candidate_id="00000000-0000-0000-0000-000000000001", role="Backend",
            salary_from_gross=1, salary_to_gross=2, contact_method="почта hr@example.ru")
    with pytest.raises(ValidationError):
        OfferCreate(
            candidate_id="00000000-0000-0000-0000-000000000001", role="Backend",
            salary_from_gross=30_000, salary_to_gross=40_000, contact_method="https://evil.example/pay")
    with pytest.raises(ValidationError):
        VacancyIn(title="Бэкенд", salary_from_gross=1, salary_to_gross=2)


def test_zero_and_order():
    assert net_monthly(0) == 0 and gross_for_net(0) == 0
    assert net_monthly(150_000) < net_monthly(250_000) < 250_000
