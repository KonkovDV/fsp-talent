from app.services.market import market_flag, quartiles


def test_four_people_publish_no_median_and_no_flag():
    assert quartiles([100, 200, 300, 400]) is None
    assert market_flag(50_000, 80_000, None) is None


def test_flags_against_a_published_median():
    cell = quartiles([100_000, 150_000, 200_000, 250_000, 300_000])
    median = cell["median"]
    assert market_flag(median, median, median) is None
    assert market_flag(40_000, median // 2 - 1, median) == "below_market"
    assert market_flag(median * 3 + 1, median * 4, median) == "suspicious"
