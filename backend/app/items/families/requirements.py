"""Requirements: steps and uncovered points. The answer is the integer the snippet prints."""
from __future__ import annotations

import random

from app.items import Family, Item, options_with


def _fill(rng: random.Random, value: int):
    def filler() -> int:
        return max(0, value + rng.choice([-3, -1, 1, 2, 4]))
    return filler


def generate(rng: random.Random, level: int, spec: str) -> Item:
    del spec, level
    stated = rng.randint(8, 40)
    covered = rng.randint(0, stated)
    ans = stated - covered
    options, correct = options_with(rng, ans, [covered, stated, ans + 1], _fill(rng, ans))
    return Item(
        stem=f"В описании {stated} требований, закрыто проверками {covered}. Сколько требований ещё без проверки?",
        options=options, correct=correct,
        explanation="Непокрытые требования — разность заявленных и уже закрытых.",
        verify={"runner": "python", "expect": str(ans),
                "code": f"print({stated} - {covered})"},
    )


FAMILY = Family(
    id="req_gaps", title="Требования: что ещё не закрыто", topic="requirements", kind="code",
    specs=frozenset({"analyst"}), skills=("A/B-тесты",), generate=generate, a=1.2,
)


def generate_steps(rng: random.Random, level: int, spec: str) -> Item:
    del spec, level
    steps = rng.randint(3, 12)
    extra = rng.randint(1, 4)
    ans = steps + extra
    options, correct = options_with(rng, ans, [steps, extra, steps * extra], _fill(rng, ans))
    return Item(
        stem=(f"В цепочке {steps} шагов. Между заявкой и ответом добавили ещё {extra} проверки. "
              "Сколько шагов стало?"),
        options=options, correct=correct,
        explanation="Новые проверки встают в цепочку, поэтому шагов становится больше на их число.",
        verify={"runner": "python", "expect": str(ans),
                "code": f"print({steps} + {extra})"},
    )


FAMILY_STEPS = Family(
    id="req_steps", title="Требования: шаги цепочки", topic="requirements", kind="code",
    specs=frozenset({"analyst"}), skills=("A/B-тесты",), generate=generate_steps, a=1.2,
)
