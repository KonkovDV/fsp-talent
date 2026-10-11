"""Blind sheet for the /evaluate «Разметить самому» mode: CSV texts plus the key's observed facts.

Run from the repo root after a new --blind-export:
    python scripts/blind_sheet_web.py docs/examples/blind_pairs_2029.csv frontend/src/data/blindSheet.json
No model score and no hidden truth: the key carries observed facts only.

The test line of the CSV is wrong for people who took the test and failed the grade: make_dataset drops
test_p, so `_candidate_card` writes «Теста нет» although skills are marked «тест». The key has no trace of
the attempt, so the generator is replayed with the export's arguments (it is deterministic) and, after
checking that it gives exactly the key's observed facts, `failed_grade` names the grade that was not passed.
If the replay does not match, the test line is dropped from those cards rather than shown wrong.
The observed facts sent to POST /public/evaluate stay the key's, so the metrics do not change.
"""
import csv
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

EXPORT = {"n_candidates": 800, "n_needs": 25, "seed": 2029}   # --blind-export --needs 25 --per-need 8 --seed 2029
NO_TEST = "Теста нет"
EXTRA = ("failed_grade", "work_formats", "city")              # drawn by the generator, not written to the key


def _same(a, b) -> bool:
    if isinstance(a, float) and isinstance(b, float):
        return math.isclose(a, b, rel_tol=1e-12)
    if isinstance(a, dict) and isinstance(b, dict):
        return a.keys() == b.keys() and all(_same(a[k], b[k]) for k in a)
    return a == b


def failed_grades(key: list[dict]) -> dict[str, str] | None:
    """pair_id → failed grade, from the replayed generator; None when the replay is not the key's dataset."""
    from app.validation.matching import make_dataset

    data = make_dataset(**EXPORT)
    by_id = {c["id"]: c["observed"] for c in data["candidates"]}
    out: dict[str, str] = {}
    for pair in key:
        replay = by_id.get(pair["candidate_id"])
        if replay is None or not _same({k: v for k, v in replay.items() if k not in EXTRA}, pair["observed"]):
            return None
        if replay.get("failed_grade"):
            out[pair["pair_id"]] = replay["failed_grade"]
    return out


def _test_line(observed: dict, failed: str | None) -> str | None:
    """The honest test line, or None when there is nothing true to say."""
    from app.validation.matching import GRADE_RU

    if observed.get("test_n"):
        return None                                   # the CSV line «верных ответов N из M» is right
    confirmed = any(v == "test_confirmed" for v in (observed.get("skills") or {}).values())
    if failed:
        line = f"Тест на грейд {GRADE_RU.get(failed, failed)} не сдан"
        return line + ", навыки с пометкой «тест» подтверждены этой попыткой" if confirmed else line
    return "" if confirmed else None                  # "" drops the line: a test happened, its result is unknown


def fix_card(card: str, observed: dict, failed: str | None) -> str:
    line = _test_line(observed, failed)
    if line is None:
        return card
    parts = card.split(". ")
    if NO_TEST not in parts:
        raise SystemExit(f"В карточке нет строки «{NO_TEST}»: {card[:60]}…")
    parts = [line if p == NO_TEST else p for p in parts]
    return ". ".join(p for p in parts if p)


def build(csv_path: str) -> dict:
    with open(csv_path, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    key = json.loads(Path(csv_path).with_suffix(".key.json").read_text(encoding="utf-8"))["pairs"]
    if [r["pair_id"] for r in rows] != [p["pair_id"] for p in key]:
        raise SystemExit("Лист и ключ из разных выгрузок")
    failed = failed_grades(key)
    needs: dict[str, dict] = {}
    pairs = []
    for row, pair in zip(rows, key, strict=True):
        need = pair["need"]
        needs.setdefault(need["id"], {**need, "text": row["need"]})
        card = fix_card(row["candidate_card"], pair["observed"], (failed or {}).get(pair["pair_id"]))
        pairs.append({"pair_id": pair["pair_id"], "need_id": need["id"], "candidate_id": pair["candidate_id"],
                      "card": card, "observed": pair["observed"]})
    return {"source": "docs/examples/blind_pairs_2029.csv + blind_pairs_2029.key.json "
                      "(--blind-export --needs 25 --per-need 8 --seed 2029); строка о тесте — по генератору",
            "needs": list(needs.values()), "pairs": pairs}


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    Path(dst).write_text(json.dumps(build(src), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
