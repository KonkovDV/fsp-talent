"""Analyst metrics: rates and averages computed from the numbers in the stem."""
from __future__ import annotations

import random

from app.items import Family, Item, options_with


def _fill(rng: random.Random, value: int):
    def filler() -> int:
        return max(0, value + rng.choice([-4, -2, 2, 3, 5, 7]))
    return filler


def generate(rng: random.Random, level: int, spec: str) -> Item:
    del spec
    if level == 1:
        visits = rng.randint(200, 2000)
        buys = rng.randint(10, visits // 5)
        ans = 100 * buys // visits
        options, correct = options_with(rng, ans, [ans + 1, max(0, ans - 1), buys, 100 - ans], _fill(rng, ans))
        return Item(
            stem=f"На сайт зашли {visits} человек, покупку оформили {buys}. Какова конверсия в целых процентах?",
            options=options, correct=correct,
            explanation="Конверсия в целых процентах — 100 × покупки // визиты.",
            verify={"runner": "python", "expect": str(ans),
                    "code": f"print(100 * {buys} // {visits})"},
        )
    if level == 2:
        n = rng.randint(4, 8)
        base = rng.randint(10, 30)
        values = [base] * n
        for i in range(n):
            values[i] = base + rng.randint(-2, 2)
        total = sum(values)
        ans = total // n
        options, correct = options_with(rng, ans, [ans + 1, max(0, ans - 1), total, values[0]], _fill(rng, ans))
        shown = ", ".join(str(v) for v in values)
        return Item(
            stem=f"Чеки за неделю, ₽: {shown}. Чему равно среднее, если дробную часть отбросить?",
            options=options, correct=correct,
            explanation="Среднее с отброшенной дробной частью — сумма // число чеков.",
            verify={"runner": "python", "expect": str(ans),
                    "code": f"xs = {values}\nprint(sum(xs) // len(xs))"},
        )
    if level == 3:
        visits = rng.randint(500, 5000)
        cart = rng.randint(visits // 5, visits // 2)
        pay = rng.randint(cart // 5, cart // 2)
        ans = 100 * pay // visits
        options, correct = options_with(rng, ans, [100 * pay // cart, 100 * cart // visits, ans + 1], _fill(rng, ans))
        return Item(
            stem=f"Воронка: визит {visits}, корзина {cart}, оплата {pay}. "
                 f"Какой целый процент визитов дошёл до оплаты?",
            options=options, correct=correct,
            explanation="Сквозная конверсия считается от первого шага, а не от корзины: 100 × оплаты // визиты.",
            verify={"runner": "python", "expect": str(ans),
                    "code": f"print(100 * {pay} // {visits})"},
        )
    if level == 4:
        weights = [rng.randint(1, 5) for _ in range(3)]
        scores = [rng.randint(2, 9) for _ in range(3)]
        ans = sum(w * s for w, s in zip(weights, scores, strict=True)) // sum(weights)
        options, correct = options_with(rng, ans, [sum(scores) // len(scores), ans + 1, scores[0]], _fill(rng, ans))
        rows = ", ".join(f"{s}×{w}" for s, w in zip(scores, weights, strict=True))
        return Item(
            stem=f"Оценки с весами: {rows}. Чему равно взвешенное среднее, если дробную часть отбросить?",
            options=options, correct=correct,
            explanation="Взвешенное среднее — сумма(оценка × вес) // сумма весов.",
            verify={"runner": "python", "expect": str(ans),
                    "code": f"s, w = {scores}, {weights}\nprint(sum(a * b for a, b in zip(s, w)) // sum(w))"},
        )
    started = rng.randint(100, 800)
    returned = rng.randint(10, started // 2)
    ans = 100 * returned // started
    options, correct = options_with(rng, ans, [ans + 1, max(0, ans - 1), returned, 100 - ans], _fill(rng, ans))
    return Item(
        stem=f"Из {started} новых пользователей на следующей неделе вернулись {returned}. "
             f"Какой целый процент составил возврат?",
        options=options, correct=correct,
        explanation="Возврат в целых процентах — 100 × вернувшиеся // новые.",
        verify={"runner": "python", "expect": str(ans),
                "code": f"print(100 * {returned} // {started})"},
    )


FAMILY = Family(
    id="analyst_metrics", title="Аналитика: конверсия и средние", topic="metrics", kind="code",
    specs=frozenset({"analyst"}), skills=("Analytics",), generate=generate, a=1.3,
)


def generate_share(rng: random.Random, level: int, spec: str) -> Item:
    """A second metrics family so a full session does not run out of items."""
    del spec, level
    parts = [rng.randint(20, 200) for _ in range(3)]
    idx = rng.randrange(3)
    ans = 100 * parts[idx] // sum(parts)
    options, correct = options_with(rng, ans, [parts[idx], ans + 1, 100 * parts[0] // sum(parts)], _fill(rng, ans))
    labels = ("A", "B", "C")
    shown = ", ".join(f"{labels[i]} {parts[i]}" for i in range(3))
    return Item(
        stem=f"Три канала, пользователи: {shown}. Какой целый процент приходится на канал {labels[idx]}?",
        options=options, correct=correct,
        explanation="Доля канала — 100 × его пользователи // сумма по каналам.",
        verify={"runner": "python", "expect": str(ans),
                "code": f"xs = {parts}\nprint(100 * xs[{idx}] // sum(xs))"},
    )


FAMILY_SHARE = Family(
    id="analyst_share", title="Аналитика: доли каналов", topic="metrics", kind="code",
    specs=frozenset({"analyst"}), skills=("Analytics",), generate=generate_share, a=1.2,
)
