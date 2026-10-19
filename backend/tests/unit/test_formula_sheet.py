from app.services.formula_sheet import formula_sheet


def test_the_sheet_is_only_for_the_demo_stand():
    assert formula_sheet(False) is None
    sheet = formula_sheet(True)
    assert sheet is not None
    assert sheet["fit"][0] == {"key": "skills", "label": "Навыки", "weight": 0.45}
    assert sheet["evidence_weight"] == 0.3
    assert {item["key"] for item in sheet["evidence"]} == {"test", "fsp"}
    assert sheet["fsp_version"] == "v4.2.0"
    assert sheet["implies"]["PostgreSQL"]["SQL"] > sheet["related_credit"]
    assert sheet["relocation_city"] == 0.7
