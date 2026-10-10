from app.services.exclusions import refused


def test_a_blocked_company_and_a_refused_sector_both_hide_the_person():
    assert refused(["fintech"], blocked=False, industry="fintech") is True
    assert refused([], blocked=True, industry=None) is True
    assert refused(["fintech"], blocked=False, industry="media") is False
    assert refused(["fintech"], blocked=False, industry="any") is False
    assert refused(["fintech"], blocked=False, industry=None) is False
