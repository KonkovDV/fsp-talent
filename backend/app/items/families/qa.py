"""Testing: boundaries, counts and coverage. The answer is the count the snippet prints."""
from __future__ import annotations

import random

from app.items import Family, Item, options_with


def _fill(rng: random.Random, value: int):
    def filler() -> int:
        shift = rng.choice([-3, -2, 2, 3, 4, 5])
        return max(0, value + shift)
    return filler


def generate(rng: random.Random, level: int, spec: str) -> Item:
    del spec
    if level == 1:
        start = rng.randint(0, 15)
        stop = start + rng.randint(4, 40)
        ans = stop - start
        options, correct = options_with(rng, ans, [ans + 1, ans - 1, stop, start], _fill(rng, ans))
        return Item(
            stem=f"Сколько раз выполнится тело цикла `for i in range({start}, {stop})`?",
            options=options, correct=correct,
            explanation="range(start, stop) не включает stop, поэтому итераций ровно stop − start.",
            verify={"runner": "python", "expect": str(ans),
                    "code": f"print(len(range({start}, {stop})))"},
        )
    if level == 2:
        lo, hi = rng.randint(10, 40), rng.randint(50, 90)
        values = [rng.randint(0, 100) for _ in range(10)]
        ans = sum(lo <= v <= hi for v in values)
        options, correct = options_with(rng, ans, [ans + 1, max(0, ans - 1), len(values), 0], _fill(rng, ans))
        shown = ", ".join(str(v) for v in values)
        return Item(
            stem=f"Какие из чисел {shown} попадают в закрытый диапазон [{lo}, {hi}]? Сколько их?",
            options=options, correct=correct,
            explanation="Закрытый диапазон включает обе границы.",
            verify={"runner": "python", "expect": str(ans),
                    "code": f"xs = {values}\nprint(sum({lo} <= v <= {hi} for v in xs))"},
        )
    if level == 3:
        n = rng.randint(5, 40)
        ans = n + 1
        options, correct = options_with(rng, ans, [n, n - 1, n + 2], _fill(rng, ans))
        return Item(
            stem=(f"Цикл начинается с i = 0 и идёт, пока i <= {n}, "
                  "затем i увеличивается на 1. Сколько итераций?"),
            options=options, correct=correct,
            explanation="Условие i <= n включает и 0, и n, поэтому итераций n + 1.",
            verify={"runner": "python", "expect": str(ans),
                    "code": f"i = 0\nc = 0\nwhile i <= {n}:\n    c += 1\n    i += 1\nprint(c)"},
        )
    if level == 4:
        total = rng.randint(50, 400)
        failed = rng.randint(1, total // 5)
        ans = 100 * failed // total
        options, correct = options_with(rng, ans, [ans + 1, max(0, ans - 1), failed, 100 - ans], _fill(rng, ans))
        return Item(
            stem=f"Прогон: {total} запросов, упало {failed}. Сколько целых процентов составляют падения?",
            options=options, correct=correct,
            explanation="Целый процент — это 100 × упавшие // все запросы, без округления вверх.",
            verify={"runner": "python", "expect": str(ans),
                    "code": f"print(100 * {failed} // {total})"},
        )
    a, b = rng.randint(2, 6), rng.randint(2, 6)
    ans = a * b
    options, correct = options_with(rng, ans, [a + b, a * b - 1, max(a, b)], _fill(rng, ans))
    return Item(
        stem=f"У параметра A {a} значений, у параметра B {b}. Сколько комбинаций в полном переборе?",
        options=options, correct=correct,
        explanation="Полный перебор двух независимых параметров — это произведение чисел значений.",
        verify={"runner": "python", "expect": str(ans), "code": f"print({a} * {b})"},
    )


FAMILY = Family(
    id="qa_checks", title="Тестирование: границы и покрытие", topic="testing", kind="code",
    specs=frozenset({"qa"}), skills=("Testing",), generate=generate, a=1.3,
)


def generate_diff(rng: random.Random, level: int, spec: str) -> Item:
    """A second testing family so a full session does not run out of items."""
    del spec, level
    expected = rng.randint(10, 80)
    delta = rng.choice([-7, -4, -2, -1, 1, 2, 5, 8])
    actual = expected + delta
    ans = abs(delta)
    options, correct = options_with(rng, ans, [delta, expected, actual, ans + 1], _fill(rng, ans))
    return Item(
        stem=f"Ожидали {expected} строк в ответе запроса, получили {actual}. На сколько строк ответ разошёлся?",
        options=options, correct=correct,
        explanation="Расхождение — модуль разности ожидаемого и фактического.",
        verify={"runner": "python", "expect": str(ans),
                "code": f"print(abs({expected} - {actual}))"},
    )


FAMILY_DIFF = Family(
    id="qa_diff", title="Тестирование: ожидаемое и фактическое", topic="testing", kind="code",
    specs=frozenset({"qa"}), skills=("Testing",), generate=generate_diff, a=1.2,
)
