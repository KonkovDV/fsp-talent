from app.services.category_rank import rank_scores


def test_the_list_is_the_test_order_without_an_identity():
    page = rank_scores([0.5, 0.91, 0.8])
    assert page["total"] == 3
    assert page["items"][0] == {"place": 1, "test": 0.91}
    assert "id" not in page["items"][0]
    assert "name" not in page["items"][0]


def test_the_page_stops_at_twenty():
    page = rank_scores([index / 100 for index in range(30)])
    assert page["total"] == 30
    assert len(page["items"]) == 20
    assert page["items"][0]["test"] == 0.29


def test_theta_breaks_a_tie_on_p_pass():
    from app.services.category_rank import rank_pairs
    page = rank_pairs([(1.0, 0.9), (1.0, 1.7), (0.92, 2.5), (1.0, None), (0.8, 0.1)])
    assert [(i["test"], i["theta"]) for i in page["items"]] == [
        (1.0, 1.7), (1.0, 0.9), (1.0, None), (0.92, 2.5), (0.8, 0.1)]
    assert page["total"] == 5 and [i["place"] for i in page["items"]] == [1, 2, 3, 4, 5]


def test_rg06_order_follows_the_shown_test_then_theta():
    """Stand regress fbcfa9a: 0.996 and 0.999 both print 1.00, so θ decides, not the hidden third digit."""
    from app.services.category_rank import rank_pairs
    page = rank_pairs([(0.999, 1.01, "a"), (0.996, 1.26, "b"), (0.994, 1.56, "c"), (0.951, 2.9, "d")])
    shown = [(i["test"], i["theta"]) for i in page["items"]]
    assert shown == [(1.0, 1.26), (1.0, 1.01), (0.99, 1.56), (0.95, 2.9)]
    for upper, lower in zip(shown, shown[1:], strict=False):
        assert upper[0] > lower[0] or (upper[0] == lower[0] and upper[1] >= lower[1])


def test_rg06_a_full_tie_is_stable_by_the_hidden_key_and_the_key_is_not_printed():
    from app.services.category_rank import rank_pairs
    rows = [(1.0, 1.2, "c"), (1.0, 1.2, "a"), (1.0, 1.2, "b")]
    one = rank_pairs(rows)
    two = rank_pairs(list(reversed(rows)))
    assert one == two
    assert all(set(item) == {"place", "test", "theta"} for item in one["items"])


def test_rg05_leaderboard_has_a_full_order():
    import inspect

    from app.api.v1 import public
    source = inspect.getsource(public.get_leaderboard)
    assert "DisciplineScore.lcb.desc(), DisciplineScore.score.desc()" in source
    assert "DisciplineScore.participant_id).limit(limit)" in source
