"""Synthetic check of the four-fifths rule. It does not read the bank and prints no live ratio.

    python -m app.validation.fairness
"""
from __future__ import annotations

from app.services.exposure_fairness import impact_report, mark_top


def main() -> None:
    scores = [0.2, 0.5, 0.9, 0.4, 0.8, 0.3, 0.7, 0.6, 0.55, 0.45]
    rows = []
    for tie, value in enumerate(scores):
        rows.append(("запад", value, tie))
        rows.append(("восток", value, tie))
    report = impact_report(mark_top(rows, 10))
    print("Регион в балл не входит. Ниже проверка правила на одинаковых баллах двух меток.")
    print(f"меньшая доля к большей: {report['min_ratio']}, порог {report['floor']}, проходит: "
          f"{'да' if report['clears'] else 'нет'}")
    print("Это не цифра живого банка.")


if __name__ == "__main__":
    main()
