from app.api.v1.needs import visible_page

ITEMS = [{"candidate_id": f"c{i}"} for i in range(5)]


def test_hidden_drop_out_and_paging_stays_on_the_rest():
    page, total = visible_page(ITEMS, {"c0", "c3"}, 0, 2, show=False)
    assert [i["candidate_id"] for i in page] == ["c1", "c2"]
    assert total == 3
    page, total = visible_page(ITEMS, {"c0", "c3"}, 2, 2, show=False)
    assert [i["candidate_id"] for i in page] == ["c4"] and total == 3


def test_show_hidden_keeps_them_marked():
    page, total = visible_page(ITEMS, {"c1"}, 0, 5, show=True)
    assert total == 5
    assert [i["candidate_id"] for i in page if i["hidden"]] == ["c1"]
    assert all("hidden" in i for i in page)
