"""Validation figures for the documentation. Every number comes from the simulators in backend/app/validation.

Run from the repository root: `python docs/tools/make_figures.py` (needs matplotlib, not a backend dependency).
Writes PNG files into docs/assets/figures. Fixed seeds: the same commit draws the same pictures.
"""
from __future__ import annotations

import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

import matplotlib  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from app.validation import assessment as va  # noqa: E402
from app.validation import matching as vm  # noqa: E402

OUT = ROOT / "docs" / "assets" / "figures"
N, SEED = 2000, 7


def clean_sessions(n: int = N, seed: int = SEED):
    """The «no leak» cohort exactly as `assessment.run` builds it."""
    rng = random.Random(seed)
    truth = va.Truth.draw(rng)
    people = va.population(n, random.Random(seed + 1))
    _, pretest = va.cohort(va.population(n, rng), truth, rng)
    offsets = va.calibrate(pretest)
    _, sessions = va.cohort(people, truth, rng, offsets=offsets)
    return sessions


def _save(fig, name: str) -> Path:
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / name
    fig.tight_layout()
    fig.savefig(path, dpi=150)
    plt.close(fig)
    return path


def se_by_theta(sessions) -> Path:
    bins: dict[float, list[float]] = {}
    for s in sessions:
        bins.setdefault(round(s.theta * 2) / 2, []).append(s.se)
    xs = sorted(k for k, v in bins.items() if len(v) >= 20)
    fig, ax = plt.subplots(figsize=(6.4, 3.8))
    ax.plot(xs, [statistics.median(bins[x]) for x in xs], marker="o")
    for cut in va.CUTS.values():
        ax.axvline(cut, color="0.8", lw=0.8)
    ax.set_xlabel("истинное θ (корзины по 0,5)")
    ax.set_ylabel("медиана SE(θ̂)")
    ax.set_title(f"Точность оценки по уровню, {len(sessions)} сессий, seed {SEED}")
    return _save(fig, "se_by_theta.png")


def theta_hat_vs_theta(sessions) -> Path:
    fig, ax = plt.subplots(figsize=(5, 5))
    ax.scatter([s.theta for s in sessions], [s.theta_hat for s in sessions], s=3, alpha=0.3)
    lo, hi = -3.5, 3.5
    ax.plot([lo, hi], [lo, hi], color="0.5", lw=0.8)
    ax.set_xlim(lo, hi)
    ax.set_ylim(lo, hi)
    ax.set_xlabel("истинное θ")
    ax.set_ylabel("оценка θ̂")
    r = statistics.correlation([s.theta for s in sessions], [s.theta_hat for s in sessions])
    ax.set_title(f"θ̂ против θ, r = {r:.3f}".replace(".", ","))
    return _save(fig, "theta_hat_vs_theta.png")


def grade_matrix(sessions) -> Path:
    grid = va.grade_matrix(sessions)
    fig, ax = plt.subplots(figsize=(5.6, 4.8))
    ax.imshow(grid, cmap="Blues")
    labels = list(va.MATRIX_LABELS)
    ax.set_xticks(range(len(labels)), labels, rotation=30)
    ax.set_yticks(range(len(labels)), labels)
    for i, row in enumerate(grid):
        for j, v in enumerate(row):
            if v:
                ax.text(j, i, str(v), ha="center", va="center", fontsize=8)
    ax.set_xlabel("присвоенный грейд")
    ax.set_ylabel("истинный грейд")
    ax.set_title("Истинный и присвоенный грейд")
    return _save(fig, "grade_matrix.png")


def adjacent_auc(sessions) -> Path:
    rows = va.adjacent_auc(sessions)
    fig, ax = plt.subplots(figsize=(6, 3.6))
    names = [f"{r.lower}/{r.upper}" for r in rows]
    ys = [r.auc for r in rows]
    err = [[r.auc - r.ci[0] for r in rows], [r.ci[1] - r.auc for r in rows]]
    ax.errorbar(names, ys, yerr=err, fmt="o", capsize=4)
    ax.axhline(0.5, color="0.8", lw=0.8)
    ax.set_ylim(0.5, 1.0)
    ax.set_ylabel("AUC (95 % ДИ)")
    ax.set_title("Разделение соседних грейдов")
    return _save(fig, "adjacent_auc.png")


def skill_stuffing() -> Path:
    rows = vm.stuffing_study(vm.make_dataset(800, 80, 2026), 0.2)
    fig, ax = plt.subplots(figsize=(6.4, 3.6))
    names = [r["method"] for r in rows]
    x = range(len(rows))
    ax.bar([i - 0.2 for i in x], [r["before"] * 100 for r in rows], width=0.4, label="до накрутки")
    ax.bar([i + 0.2 for i in x], [r["top"] * 100 for r in rows], width=0.4, label="после")
    ax.set_xticks(list(x), names)
    ax.set_ylabel("доля в топ-10, %")
    ax.set_title("Накрутка навыков: 20 % кандидатов")
    ax.legend()
    return _save(fig, "skill_stuffing.png")


def main() -> None:
    sessions = clean_sessions()
    for path in (se_by_theta(sessions), theta_hat_vs_theta(sessions), grade_matrix(sessions),
                 adjacent_auc(sessions), skill_stuffing()):
        print(path.relative_to(ROOT))


if __name__ == "__main__":
    main()
