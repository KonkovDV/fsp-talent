"""Matching on an external set with human rankings: `python -m app.validation.external_human`.

The set: 30 anonymised English resumes and 5 software-developer vacancies; two annotators ranked the five
vacancies for every resume (1 = most relevant) after an HR specialist's guidelines (Vanetik & Kogan 2023,
doi:10.3390/info14080468). It is GPL-3.0 and is NOT part of this repository: the command downloads it from a
pinned commit into a cache under /tmp and checks the sha256 of every file. Without network it says so.

Every method ranks the five vacancies for each resume. Ours is the text part of the product score
(`services.matching.score` with skills from `services.skills.extract_skills`, trust "resume", and the lexical
factor from BM25); the test and the FSP axis are absent on this data. Baselines: BM25 alone, TF-IDF cosine,
skill coverage alone, random order (expectation over 2000 fixed-seed shuffles). Metrics against the average
human rank (as in the paper) and against each annotator: Spearman ρ, Kendall τ-b, nDCG@5 (gain 5 − mean rank),
top-1 hit. Ceiling: agreement of the two annotators with each other. Järvelin & Kekäläinen 2002,
doi:10.1145/582415.582418 (nDCG); Kendall 1945 (τ-b).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import io
import math
import os
import random
import re
import statistics
import sys
import urllib.error
import urllib.request
import zipfile
from collections.abc import Callable
from pathlib import Path

from app.services.matching import CandidateFacts, NeedSpec, score
from app.services.search.bm25 import bm25, tokens
from app.services.skills import extract_skills

REPO = "NataliaVanetik/vacancy-resume-matching-dataset"
COMMIT = "7ee8f043c6e31ee94cb67f5e60b069901b533adf"
LICENSE = "GPL-3.0"
CACHE = Path(os.environ.get("EXTERNAL_HUMAN_CACHE", "/tmp/external-human-" + COMMIT[:7]))
VACANCIES = "5_vacancies.csv"
ANNOTATIONS = "annotations-for-the-first-30-vacancies.txt"
RESUMES = 30
SHA256 = {
    "5_vacancies.csv": "e14d2e5052e8bb4884514b066b17be0bf789f4f0bd79d942e6d7a49e101dbaa4",
    "annotations-for-the-first-30-vacancies.txt": "938ff4089918807809f8920e16d4433d2267fe8104f9641b477163f4a157293b",
    "CV/1.docx": "97ea8f68a1980096051cfaf4b67854967720b693a2c7b3ee5e8bea2ca3249db2",
    "CV/2.docx": "9352f408868361f4c94bc7c7315beefa1a16189ece528b7305e366897e486875",
    "CV/3.docx": "08b5730f480ec1682d793a6a07d96a31a32fd782ce58164008d2a3fb4fe60e06",
    "CV/4.docx": "b6629206356e0f1b573b3b3eab5282d20b7cb185f5b392d6d0cac83099176e89",
    "CV/5.docx": "a8467a72215a723f0832b5ebcba300ed5d713c6f13d3fd109059f69a63562225",
    "CV/6.docx": "20c211435ce3aa684d98000ddc15c3bd8ff1734b43de393d016e70c8e04bbd2d",
    "CV/7.docx": "29a1196feb8cfaeb5dc9db35de9738e1b934606a71c65bf0628dd68e4c99ce9a",
    "CV/8.docx": "f5a98824cedb7e0b67ace2b9e7e20024f74099105b2190cbe021eb95a9193c3c",
    "CV/9.docx": "7da853eb897134efc123da081a62aa2350376d80c0ee4a21ab7f15ae925a5121",
    "CV/10.docx": "a1c3877a5da460f8ed51c45e3c8be2b03c7bafeba789649beb1f36161f689654",
    "CV/11.docx": "6c0f3d43c194ccb0fedb1c42050914107c19172adb4bf3107323760380dadcd8",
    "CV/12.docx": "160faebb9c8c4106c2977285a9042c5cd7220963b7715e80c53c61f194d4b72f",
    "CV/13.docx": "ab204a3bb4634112e5cabc29a7368b54cefc76ffbfa6ebaafa89c118fc3f4eab",
    "CV/14.docx": "7c66ef39d8ba011404ad3bd170de1c0eece089d756da56bf3191fbb1313f47f5",
    "CV/15.docx": "e9c8c8abecdb44adf388d7367d936b39896daf696bb2bf6e041db4cde807241e",
    "CV/16.docx": "45aba9525dfbbbeade2243837ed0df20f081b521cc39ec925163f81c6ab9eb30",
    "CV/17.docx": "7103f72150f4523117a5b217397e37768f92adf12833242d8b1aae9545d762cb",
    "CV/18.docx": "6dc7618faec028ee9857a05942b229aa4a256a578700cf35984c6683d5fe769a",
    "CV/19.docx": "90b3713df35065e5babbf95541a07ab237cc98e7ab2744654dd738ceebe4e1dd",
    "CV/20.docx": "65624dddeb91462b171a40b1ac8406112abb7842a1a437ef08495defa072036e",
    "CV/21.docx": "19e6592c426739e97aefaf238b050990cc24741d0298a0da6c4e79a3915c780e",
    "CV/22.docx": "091960aec6a56e340c11941c7edbf6f55df59deec60574b2b830bc63341c0e9c",
    "CV/23.docx": "619925575c38265e54615ffc55ae9c4eb7e0b694900e2ceb0f0c3a5902747fb7",
    "CV/24.docx": "db4653bc7f1687321bfd7763f1f5bc51bb0019a690c4220f1d28ca836b9ec3aa",
    "CV/25.docx": "f5b1081d835bb72462b23dc6422aa56821c9b9a55f32319be8aa137e1bd08d98",
    "CV/26.docx": "0cfc4d6da4904ed299dfaa3634a5c48e9e2b0b7bc53787840973f3b946796f4c",
    "CV/27.docx": "1e497159545354a65d0714eda186e9f7a2158033d8d1f5d1a7f94cc2215972f3",
    "CV/28.docx": "8695b58c2e1e1a17270bc8b8dbf99bf1b905242d2dba07caacc8556c2bde347a",
    "CV/29.docx": "7e8cd20d4f137af5868beee6f4c8649d88f3bc6716cb74f53ceb6f2de534cf89",
    "CV/30.docx": "5cf5bf278dd6e8c5e05f325dc70d10f34876eef554da6c1d6af564455ca45134",
}


class DatasetError(RuntimeError):
    """The set could not be fetched or does not match the pinned hashes."""


def _url(name: str) -> str:
    return f"https://raw.githubusercontent.com/{REPO}/{COMMIT}/{name}"


def fetch(cache: Path = CACHE, opener: Callable[[str], bytes] | None = None) -> Path:
    """Download the pinned files once; every file must match its sha256."""
    def default(url: str) -> bytes:
        with urllib.request.urlopen(url, timeout=30) as r:  # noqa: S310 - fixed https host
            return r.read()
    opener = opener or default
    for name, want in SHA256.items():
        path = cache / name
        if path.exists() and hashlib.sha256(path.read_bytes()).hexdigest() == want:
            continue
        try:
            data = opener(_url(name))
        except (urllib.error.URLError, OSError) as exc:
            raise DatasetError(f"нет доступа к {_url(name)}: {exc}") from exc
        got = hashlib.sha256(data).hexdigest()
        if got != want:
            raise DatasetError(f"{name}: sha256 {got[:12]}… вместо {want[:12]}…")
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    return cache


def docx_text(data: bytes) -> str:
    """Plain text of a .docx: paragraphs of word/document.xml, standard library only."""
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        xml = z.read("word/document.xml").decode("utf-8", "replace")
    xml = re.sub(r"</w:p>|<w:br[^>]*/>|<w:tab[^>]*/>", "\n", xml)
    return re.sub(r"[ \t]+", " ", html.unescape(re.sub(r"<[^>]+>", "", xml))).strip()


def parse_annotations(text: str) -> tuple[list[list[int]], list[list[int]]]:
    """Two lists of 30 arrays. Position i is vacancy i (row order of the csv), the value is its rank.

    The paper averages the arrays position by position, so a position is a vacancy; equal values are ties.
    """
    out = []
    for name in ("ANNOTATOR_1_RANKINGS", "ANNOTATOR_2_RANKINGS"):
        m = re.search(name + r"\s*=\s*(\[.*?\]\])", text, re.S)
        if not m:
            raise DatasetError(f"нет {name}")
        rows = [[int(x) for x in re.findall(r"\d+", row)] for row in re.findall(r"\[([\d,\s]+)\]", m.group(1))]
        if len(rows) != RESUMES or any(len(r) != 5 for r in rows):
            raise DatasetError(f"{name}: ожидалось {RESUMES} массивов по 5")
        out.append(rows)
    return out[0], out[1]


def load(cache: Path) -> tuple[list[dict], list[str], list[list[int]], list[list[int]]]:
    with open(cache / VACANCIES, newline="", encoding="utf-8") as f:
        vacancies = list(csv.DictReader(f))
    resumes = [docx_text((cache / f"CV/{i}.docx").read_bytes()) for i in range(1, RESUMES + 1)]
    a1, a2 = parse_annotations((cache / ANNOTATIONS).read_text(encoding="utf-8"))
    return vacancies, resumes, a1, a2


# ---- statistics -------------------------------------------------------------------------------------------

def _ranks(values: list[float]) -> list[float]:
    """Average ranks, 1 = smallest."""
    order = sorted(range(len(values)), key=lambda i: values[i])
    ranks = [0.0] * len(values)
    i = 0
    while i < len(order):
        j = i
        while j + 1 < len(order) and values[order[j + 1]] == values[order[i]]:
            j += 1
        for k in range(i, j + 1):
            ranks[order[k]] = (i + j) / 2 + 1
        i = j + 1
    return ranks


def spearman(x: list[float], y: list[float]) -> float | None:
    rx, ry = _ranks(x), _ranks(y)
    mx, my = statistics.mean(rx), statistics.mean(ry)
    sx = math.sqrt(sum((a - mx) ** 2 for a in rx))
    sy = math.sqrt(sum((b - my) ** 2 for b in ry))
    if sx == 0 or sy == 0:
        return None
    return sum((a - mx) * (b - my) for a, b in zip(rx, ry, strict=True)) / (sx * sy)


def kendall_tau_b(x: list[float], y: list[float]) -> float | None:
    conc = disc = tx = ty = 0
    n = len(x)
    for i in range(n):
        for j in range(i + 1, n):
            dx, dy = x[i] - x[j], y[i] - y[j]
            if dx == 0 and dy == 0:
                continue
            if dx == 0:
                tx += 1
            elif dy == 0:
                ty += 1
            elif dx * dy > 0:
                conc += 1
            else:
                disc += 1
    denom = math.sqrt((conc + disc + tx) * (conc + disc + ty))
    return None if denom == 0 else (conc - disc) / denom


def ndcg(order: list[int], gains: list[float]) -> float:
    """nDCG over the whole list; `order` lists item indices best first."""
    dcg = sum(gains[i] / math.log2(k + 2) for k, i in enumerate(order))
    ideal = sum(g / math.log2(k + 2) for k, g in enumerate(sorted(gains, reverse=True)))
    return dcg / ideal if ideal > 0 else 1.0


# ---- methods: a higher score is a better vacancy for the resume ----------------------------------------------

def _vacancy_text(v: dict) -> str:
    return f"{v['job_title']}\n{v['job_description']}"


def _tfidf(docs: list[list[str]]) -> list[dict[str, float]]:
    df: dict[str, int] = {}
    for d in docs:
        for t in set(d):
            df[t] = df.get(t, 0) + 1
    n = len(docs)
    out = []
    for d in docs:
        tf: dict[str, int] = {}
        for t in d:
            tf[t] = tf.get(t, 0) + 1
        vec = {t: (1 + math.log(c)) * math.log((1 + n) / (1 + df[t])) + 0.0 for t, c in tf.items()}
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        out.append({t: v / norm for t, v in vec.items()})
    return out


def method_scores(vacancies: list[dict], resumes: list[str]) -> dict[str, list[list[float]]]:
    vtexts = [_vacancy_text(v) for v in vacancies]
    vskills = [tuple(dict.fromkeys(s.skill for s in extract_skills(t))) for t in vtexts]
    vecs = _tfidf([tokens(t) for t in vtexts + resumes])
    out: dict[str, list[list[float]]] = {"product": [], "bm25": [], "tfidf": [], "skills": []}
    for r_index, resume in enumerate(resumes):
        lexical = bm25(resume, vtexts)
        top = max(lexical) or 1.0
        have = {s.skill: "resume_confirmed" for s in extract_skills(resume)}
        product, coverage = [], []
        for j, skills in enumerate(vskills):
            facts = CandidateFacts(role=None, grade=None, grade_source=None, skills=have,
                                   text_rank=lexical[j] / top)
            product.append(score(NeedSpec(skills=skills, text=True), facts).score)
            coverage.append(sum(s in have for s in skills) / len(skills) if skills else 0.0)
        rv = vecs[len(vtexts) + r_index]
        out["product"].append(product)
        out["bm25"].append(lexical)
        out["tfidf"].append([sum(w * rv.get(t, 0.0) for t, w in vecs[j].items()) for j in range(len(vtexts))])
        out["skills"].append(coverage)
    return out


def _order(scores: list[float]) -> list[int]:
    return sorted(range(len(scores)), key=lambda i: (-scores[i], i))


def evaluate(scores: list[list[float]], a1: list[list[int]], a2: list[list[int]]) -> dict[str, float]:
    """Mean over resumes. Human ranks are turned into scores by negation (rank 1 is the best)."""
    rho, tau, tau1, tau2, nd, top1 = [], [], [], [], [], []
    for s, r1, r2 in zip(scores, a1, a2, strict=True):
        mean_rank = [(x + y) / 2 for x, y in zip(r1, r2, strict=True)]
        human = [-m for m in mean_rank]
        for bucket, ref in ((rho, None), (tau, human), (tau1, [-x for x in r1]), (tau2, [-x for x in r2])):
            value = spearman(s, human) if ref is None else kendall_tau_b(s, ref)
            if value is not None:
                bucket.append(value)
        order = _order(s)
        nd.append(ndcg(order, [5 - m for m in mean_rank]))
        top1.append(mean_rank[order[0]] == min(mean_rank))
    return {"rho": statistics.mean(rho), "tau": statistics.mean(tau), "tau_a1": statistics.mean(tau1),
            "tau_a2": statistics.mean(tau2), "ndcg5": statistics.mean(nd), "top1": sum(top1) / len(top1)}


def random_baseline(a1: list[list[int]], a2: list[list[int]], draws: int = 2000, seed: int = 2026) -> dict:
    rng = random.Random(seed)
    rows = []
    for _ in range(draws):
        rows.append(evaluate([[rng.random() for _ in range(5)] for _ in a1], a1, a2))
    return {k: statistics.mean(r[k] for r in rows) for k in rows[0]}


def annotator_agreement(a1: list[list[int]], a2: list[list[int]]) -> dict[str, float]:
    rho = [v for v in (spearman(x, y) for x, y in zip(a1, a2, strict=True)) if v is not None]
    tau = [v for v in (kendall_tau_b(x, y) for x, y in zip(a1, a2, strict=True)) if v is not None]
    top = sum(x.index(min(x)) == y.index(min(y)) for x, y in zip(a1, a2, strict=True)) / len(a1)
    return {"rho": statistics.mean(rho), "tau": statistics.mean(tau), "top1": top}


def bootstrap_diff(left: list[list[float]], right: list[list[float]], a1, a2, key: str = "tau",
                   draws: int = 1000, seed: int = 2026) -> tuple[float, float, float]:
    """Paired bootstrap over resumes of the difference of a mean metric (left − right)."""
    rng = random.Random(seed)
    n = len(a1)
    base = evaluate(left, a1, a2)[key] - evaluate(right, a1, a2)[key]
    diffs = []
    for _ in range(draws):
        idx = [rng.randrange(n) for _ in range(n)]
        pick = lambda rows: [rows[i] for i in idx]  # noqa: E731
        diffs.append(evaluate(pick(left), pick(a1), pick(a2))[key] - evaluate(pick(right), pick(a1), pick(a2))[key])
    diffs.sort()
    return base, diffs[int(0.025 * draws)], diffs[int(0.975 * draws) - 1]


NAMES = {"product": "Текстовая часть оценки продукта (навыки + BM25)", "bm25": "BM25 (резюме как запрос)",
         "tfidf": "TF-IDF, косинус", "skills": "Только покрытие навыков вакансии", "random": "Случайный порядок"}


def report(cache: Path = CACHE) -> str:
    vacancies, resumes, a1, a2 = load(fetch(cache))
    scores = method_scores(vacancies, resumes)
    rows = {name: evaluate(s, a1, a2) for name, s in scores.items()}
    rows["random"] = random_baseline(a1, a2)
    agree = annotator_agreement(a1, a2)
    lines = [f"Набор {REPO}@{COMMIT[:7]} ({LICENSE}, не входит в репозиторий), {len(resumes)} резюме × "
             f"{len(vacancies)} вакансий, два разметчика. Все sha256 совпали.", "",
             "| Способ | Спирмен ρ со средним рангом | τ-b со средним | τ-b с разметчиком 1 | τ-b с разметчиком 2 "
             "| nDCG@5 | Топ-1 совпал |", "|---|---|---|---|---|---|---|"]
    for name in ("product", "bm25", "tfidf", "skills", "random"):
        r = rows[name]
        lines.append(f"| {NAMES[name]} | {r['rho']:.3f} | {r['tau']:.3f} | {r['tau_a1']:.3f} | {r['tau_a2']:.3f} | "
                     f"{r['ndcg5']:.3f} | {r['top1'] * 100:.1f}% |")
    lines += ["", f"Согласие разметчиков между собой (потолок): Спирмен ρ {agree['rho']:.3f}, τ-b {agree['tau']:.3f}, "
              f"топ-1 совпал у {agree['top1'] * 100:.1f}% резюме.", ""]
    for other in ("bm25", "tfidf"):
        d, lo, hi = bootstrap_diff(scores["product"], scores[other], a1, a2)
        lines.append(f"Продукт минус {NAMES[other]}, τ-b со средним: {d:+.3f} (95 % ДИ {lo:+.3f}…{hi:+.3f}, "
                     "парный бутстреп по резюме, 1000 повторов)")
    vskills = [sorted({s.skill for s in extract_skills(_vacancy_text(v))}) for v in vacancies]
    lines += ["", "Навыки, извлечённые из вакансий: " + "; ".join(
        f"{v['job_title']} — {len(s)}" for v, s in zip(vacancies, vskills, strict=True)),
        "Навыков в резюме (медиана): " + f"{statistics.median(len(extract_skills(r)) for r in resumes):g}"]
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cache", type=Path, default=CACHE)
    args = parser.parse_args()
    try:
        print(report(args.cache))
    except DatasetError as exc:
        print(f"Внешний набор недоступен: {exc}", file=sys.stderr)
        raise SystemExit(2) from None


if __name__ == "__main__":
    main()
