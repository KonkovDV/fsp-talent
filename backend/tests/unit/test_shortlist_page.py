from app.api.v1.needs import shortlist_page

ITEMS = [
    {"candidate_id": "a", "status": "shortlisted"},
    {"candidate_id": "b", "status": "invited"},
    {"candidate_id": "c", "status": "rejected"},
]


def test_without_a_status_the_whole_list_stays():
    assert shortlist_page(ITEMS, None) == ITEMS


def test_a_status_keeps_only_that_step():
    assert [item["candidate_id"] for item in shortlist_page(ITEMS, "invited")] == ["b"]
