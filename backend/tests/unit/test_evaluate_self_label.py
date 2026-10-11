"""/evaluate «Разметить самому»: the blind sheet on the page and P@5 in public_report."""
import importlib.util
import json
from pathlib import Path

import pytest

from app.validation.matching import public_report

ROOT = Path(__file__).resolve().parents[3]
SHEET = ROOT / "frontend" / "src" / "data" / "blindSheet.json"
CSV = ROOT / "docs" / "examples" / "blind_pairs_2029.csv"
MERGED = ROOT / "docs" / "examples" / "ai_raters_merged.jsonl"

needs_repo = pytest.mark.skipif(not (SHEET.exists() and CSV.exists() and MERGED.exists()),
                                reason="нужен полный репозиторий: frontend и docs")


def _page_lines(sheet: dict, need_id: str, labels: dict[tuple[str, str], int]) -> str:
    """The JSONL the page sends: same shape as the upload mode, need without its card text."""
    need = next(n for n in sheet["needs"] if n["id"] == need_id)
    need = {k: need[k] for k in ("id", "role", "grade", "skills")}
    return "\n".join(json.dumps({"need": need, "candidate_id": p["candidate_id"],
                                 "candidate": {"observed": p["observed"]},
                                 "label": labels[(need_id, p["candidate_id"])]}, ensure_ascii=False)
                     for p in sheet["pairs"] if p["need_id"] == need_id)


@needs_repo
def test_page_sheet_is_the_blind_export():
    spec = importlib.util.spec_from_file_location("blind_sheet_web", ROOT / "scripts" / "blind_sheet_web.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sheet = json.loads(SHEET.read_text(encoding="utf-8"))
    assert sheet == module.build(str(CSV))
    assert len(sheet["needs"]) == 25 and len(sheet["pairs"]) == 200
    for pair in sheet["pairs"]:
        assert set(pair) == {"pair_id", "need_id", "candidate_id", "card", "observed"}
        assert "truth" not in pair["observed"] and "score" not in pair["observed"]


@needs_repo
def test_one_need_from_the_page_gives_p5_from_the_model_top():
    sheet = json.loads(SHEET.read_text(encoding="utf-8"))
    labels = {}
    for line in MERGED.read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        labels[(row["need"]["id"], row["candidate_id"])] = row["label"]
    report = public_report(_page_lines(sheet, "n0", labels))
    assert report["pairs"] == 8 and report["needs"] == 1
    rows = {row["method"]: row for row in report["rows"]}
    assert set(rows) == {"full", "keyword", "random"}
    assert all(0.0 <= row["p5"] <= 1.0 for row in rows.values())
    top = report["per_need"][0]["top"]
    assert len(top) == 5
    assert rows["full"]["p5"] == round(sum(1 for t in top if t["label"] >= 2) / 5, 4)


def test_p5_counts_all_seats_when_fewer_than_five():
    need = {"id": "n", "role": "backend", "grade": "middle", "skills": ["Python"]}
    observed = {"role": "backend", "grade": "middle", "grade_source": "assessed",
                "skills": {"Python": "test_confirmed"}, "test_p": 0.9, "fsp_lcb": 0.5, "industry": "fintech"}
    text = "\n".join(json.dumps({"need": need, "candidate_id": f"c{i}", "candidate": {"observed": observed},
                                 "label": label}) for i, label in enumerate((3, 2)))
    report = public_report(text)
    assert all(row["p5"] == 1.0 for row in report["rows"])
