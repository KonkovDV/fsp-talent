from types import SimpleNamespace

from app.services.trust_level import invite_limit, trust_level, vacancy_limit

COMPANY = dict(email="hr@sibcode.demo", website="https://www.sibcode.demo/about", inn=None, fsp_partner=False)


def test_domain_match_beats_a_bare_tax_id_and_partner_beats_both():
    assert trust_level(SimpleNamespace(**COMPANY)) == 2
    assert trust_level(SimpleNamespace(**{**COMPANY, "website": "other.ru"})) == 0
    assert trust_level(SimpleNamespace(**{**COMPANY, "website": None, "fsp_partner": True})) == 3


def test_limits_follow_the_level():
    assert invite_limit(0) == 10 and invite_limit(1) == 50
    assert vacancy_limit(0) == 1 and vacancy_limit(2) == 10 and vacancy_limit(3) == 30


def test_a_valid_inn_is_level_one_without_claiming_the_registry():
    from app.services.inn import inn_is_valid
    # 7707083893 is a well-known checksum example (Yandex).
    assert inn_is_valid("7707083893")
    assert trust_level(SimpleNamespace(email="a@b.ru", website=None, inn="7707083893", fsp_partner=False)) == 1
