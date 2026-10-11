"""Blind sheet for the /evaluate «Разметить самому» mode: CSV texts plus the key's observed facts.

Run from the repo root after a new --blind-export:
    python scripts/blind_sheet_web.py docs/examples/blind_pairs_2029.csv frontend/src/data/blindSheet.json
No model score and no hidden truth: the key carries observed facts only.
"""
import csv
import json
import sys
from pathlib import Path


def build(csv_path: str) -> dict:
    with open(csv_path, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    key = json.loads(Path(csv_path).with_suffix(".key.json").read_text(encoding="utf-8"))["pairs"]
    if [r["pair_id"] for r in rows] != [p["pair_id"] for p in key]:
        raise SystemExit("Лист и ключ из разных выгрузок")
    needs: dict[str, dict] = {}
    pairs = []
    for row, pair in zip(rows, key, strict=True):
        need = pair["need"]
        needs.setdefault(need["id"], {**need, "text": row["need"]})
        pairs.append({"pair_id": pair["pair_id"], "need_id": need["id"], "candidate_id": pair["candidate_id"],
                      "card": row["candidate_card"], "observed": pair["observed"]})
    return {"source": "docs/examples/blind_pairs_2029.csv + blind_pairs_2029.key.json "
                      "(--blind-export --needs 25 --per-need 8 --seed 2029)",
            "needs": list(needs.values()), "pairs": pairs}


if __name__ == "__main__":
    src, dst = sys.argv[1], sys.argv[2]
    Path(dst).write_text(json.dumps(build(src), ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
