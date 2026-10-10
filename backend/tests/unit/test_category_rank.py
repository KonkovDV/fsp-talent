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
