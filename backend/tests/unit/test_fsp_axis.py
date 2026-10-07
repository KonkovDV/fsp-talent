"""The axis validation: a farm of online appearances stays under two wins, and empty protocols drop out."""
from app.services.scoring.engine import compute_discipline_score
from app.validation.fsp_axis import REF, farm, farm_is_under_two_wins, population


def test_forty_online_appearances_stay_under_two_wins():
    padded, wins, ok = farm_is_under_two_wins()
    assert ok
    assert round(padded, 2) == 0.01
    assert round(wins, 2) == 0.54


def test_the_cap_stops_the_farm_growing():
    five = compute_discipline_score(farm(5), REF)["lcb"]
    forty = compute_discipline_score(farm(40), REF)["lcb"]
    assert forty == five


def test_people_without_a_protocol_are_not_in_the_correlation():
    skills, lcbs, places, counts, skipped = population(40, 3)
    assert len(skills) == len(lcbs) == len(places) == len(counts)
    assert len(skills) + skipped == 40
    assert all(count >= 1 for count in counts)
