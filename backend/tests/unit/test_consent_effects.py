from app.services.consent_effects import planned_effects


def test_withdrawing_processing_names_the_search_the_contacts_and_the_erasure():
    codes = [item["code"] for item in planned_effects("participant", "pd_candidate")]
    assert codes == ["hide_card", "close_contacts", "erase_in_30_days"]
    assert "30 дней" in planned_effects("participant", "pd_candidate")[-1]["text"]


def test_distribution_does_not_claim_to_hide_the_search_card():
    items = planned_effects("participant", "pd_distribution")
    assert items[0]["code"] == "public_page_off"
    assert "поиске" in items[0]["text"]


def test_distribution_withdrawal_names_the_fsp_id_lookup():
    items = planned_effects("participant", "pd_distribution")
    assert [item["code"] for item in items] == ["public_page_off", "fsp_lookup_off"]
    assert "ФСП ID" in items[1]["text"]
