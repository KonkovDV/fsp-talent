from app.services.desk import can_suspend, complaints_csv


def test_the_desk_cannot_switch_off_itself_or_the_printed_employer():
    assert can_suspend("a", "b", "other@demo.talent")
    assert not can_suspend("a", "a", "other@demo.talent")
    assert not can_suspend("a", "b", "hr@sibcode.demo")


def test_the_complaint_export_has_no_person_column():
    text = complaints_csv([{
        "id": "c1", "reason": "fake", "vacancy_id": "v1", "offer_id": None, "created_at": "2026-10-10T00:00:00+00:00",
    }])
    assert text.splitlines()[0] == "id,reason,vacancy_id,offer_id,created_at"
    assert "participant" not in text
    assert "c1,fake,v1,," in text.splitlines()[1]
