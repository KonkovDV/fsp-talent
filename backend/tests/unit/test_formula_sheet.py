from app.services.formula_sheet import formula_sheet


def test_the_sheet_is_only_for_the_demo_stand():
    assert formula_sheet(False) is None
    sheet = formula_sheet(True)
    assert sheet is not None
    assert sheet["fit"][0] == {"key": "skills", "label": "Навыки", "weight": 0.5}
    assert sheet["evidence_weight"] == 0.4
    assert {item["key"] for item in sheet["evidence"]} == {"test", "fsp"}
