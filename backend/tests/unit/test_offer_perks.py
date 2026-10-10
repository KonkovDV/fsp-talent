from app.services.offer_perks import clean_perks


def test_unknown_and_repeated_perks_are_dropped():
    assert clean_perks(["fsp_tournaments", "elo", "fsp_tournaments", "health"]) == ["fsp_tournaments", "health"]
    assert "elo" not in clean_perks(["elo"])
