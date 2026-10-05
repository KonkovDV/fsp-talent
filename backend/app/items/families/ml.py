"""Machine learning: metrics and one optimisation step, computed from the given numbers."""
from __future__ import annotations

import math
import random

from app.items import Family, Item, options_with


def _fmt(x: float) -> str:
    return f"{x:.2f}"


def _num_filler(rng, value):
    return lambda: _fmt(max(0.0, value + rng.choice([-1, 1]) * rng.uniform(0.04, 0.2)))


def generate(rng: random.Random, level: int, spec: str) -> Item:
    tp, fp, fn, tn = rng.randint(10, 60), rng.randint(3, 30), rng.randint(3, 30), rng.randint(20, 90)
    matrix = f"TP = {tp}, FP = {fp}, FN = {fn}, TN = {tn}"
    acc = (tp + tn) / (tp + fp + fn + tn)
    prec, rec = tp / (tp + fp), tp / (tp + fn)
    f1 = 2 * prec * rec / (prec + rec)
    if level in (1, 2, 3):
        name, value, wrong, why = {
            1: ("accuracy", acc, [prec, rec, tp / (tp + fp + fn + tn)], "(TP + TN) / все объекты."),
            2: ("precision", prec, [rec, acc, tn / (tn + fp)], "TP / (TP + FP): доля верных среди предсказанных "
                                                                "положительных."),
            3: ("F1", f1, [(prec + rec) / 2, acc, min(prec, rec)], "Гармоническое среднее precision и recall."),
        }[level]
        options, correct = options_with(rng, _fmt(value), [_fmt(w) for w in wrong], _num_filler(rng, value))
        return Item(stem=f"Матрица ошибок классификатора: {matrix}. Чему равен {name} (два знака)?",
                    options=options, correct=correct, explanation=why,
                    verify={"runner": "python", "expect": _fmt(value), "code": (
                        f"tp, fp, fn, tn = {tp}, {fp}, {fn}, {tn}\np, r = tp / (tp + fp), tp / (tp + fn)\n"
                        + {1: "v = (tp + tn) / (tp + fp + fn + tn)", 2: "v = p", 3: "v = 2 * p * r / (p + r)"}[level]
                        + "\nprint(f'{v:.2f}')")})
    if level == 4:
        xs = [rng.randint(1, 4) for _ in range(3)]
        w0 = rng.choice([0.0, 0.5, 1.0])
        true_w = rng.choice([2, 3])
        ys = [true_w * x + rng.choice([-1, 0, 1]) for x in xs]
        lr = rng.choice([0.01, 0.05, 0.1])
        grad = sum(2 * (w0 * x - y) * x for x, y in zip(xs, ys, strict=True)) / len(xs)
        w1 = w0 - lr * grad
        wrong = [w0 + lr * grad, w0 - grad, w0 - lr * grad / len(xs)]
        pts = ", ".join(f"({x}, {y})" for x, y in zip(xs, ys, strict=True))
        options, correct = options_with(rng, _fmt(w1), [_fmt(w) for w in wrong], _num_filler(rng, w1))
        return Item(stem=f"Модель y = w·x, функция потерь MSE = mean((w·x − y)²). Точки: {pts}. "
                         f"w = {w0}, шаг обучения {lr}. Чему равно w после одного шага градиентного спуска?",
                    options=options, correct=correct,
                    explanation="dMSE/dw = mean(2·(w·x − y)·x); w ← w − lr·градиент.",
                    verify={"runner": "python", "expect": _fmt(w1), "code": (
                        f"xs, ys, w, lr = {xs}, {ys}, {w0}, {lr}\n"
                        "g = sum(2 * (w * x - y) * x for x, y in zip(xs, ys)) / len(xs)\nprint(f'{w - lr * g:.2f}')")})
    logits = [round(rng.uniform(-1, 3), 1) for _ in range(3)]
    k = rng.randrange(3)
    exps = [math.exp(z) for z in logits]
    p = exps[k] / sum(exps)
    wrong = [logits[k] / sum(logits) if sum(logits) else 0.5, 1 / 3, max(exps) / sum(exps)]
    options, correct = options_with(rng, _fmt(p), [_fmt(w) for w in wrong], _num_filler(rng, p))
    return Item(stem=f"Логиты трёх классов: {logits}. Какую вероятность даёт softmax классу {k + 1} (два знака)?",
                options=options, correct=correct, explanation="softmax(z)_k = e^{z_k} / Σ e^{z_j}.",
                verify={"runner": "python", "expect": _fmt(p), "code": (
                    f"import math\nz = {logits}\ne = [math.exp(v) for v in z]\nprint(f'{{e[{k}] / sum(e):.2f}}')")})


FAMILY = Family(
    id="ml_metrics", title="ML: метрики и оптимизация", topic="ml", kind="code",
    specs=frozenset({"ml"}), skills=("Machine Learning",), generate=generate, a=1.4,
)
