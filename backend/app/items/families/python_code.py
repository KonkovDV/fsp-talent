"""Python: what does the snippet print. The answer is obtained by running the snippet."""
from __future__ import annotations

import contextlib
import io
import random

from app.items import Family, Item, near_int, options_with


def run_python(code: str) -> str:
    """Run one of our own templates (never user input) and return what it printed."""
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        exec(compile(code, "<item>", "exec"), {"__name__": "__item__"})  # noqa: S102 - trusted template
    return out.getvalue().strip()


def _item(rng, code, distractors, explanation, spread=6) -> Item:
    answer = run_python(code)
    value = int(answer) if answer.lstrip("-").isdigit() else None
    filler = near_int(rng, value, spread) if value is not None else None
    options, correct = options_with(rng, answer, distractors, filler)
    return Item(stem="Что выведет код?", code=code, language="python", options=options, correct=correct,
                explanation=explanation, verify={"runner": "python", "code": code, "expect": answer})


def generate(rng: random.Random, level: int, spec: str) -> Item:
    if level == 1:
        a, b = rng.randint(17, 99), rng.randint(3, 9)
        code = f"a = {a}\nb = {b}\nprint(a // b + a % b)"
        return _item(rng, code, [a // b, a % b, round(a / b) + a % b, a // b * b],
                     f"// — целочисленное деление ({a // b}), % — остаток ({a % b}).")
    if level == 2:
        n, i, j, k = rng.randint(10, 16), rng.randint(1, 3), rng.randint(6, 9), rng.randint(2, 3)
        code = f"xs = list(range({n}))\nprint(sum(xs[{i}:{j}:{k}]))"
        incl = sum(range(i, j + 1, k))
        no_step = sum(range(i, j))
        from_one = sum(range(i + 1, j + 1, k))
        return _item(rng, code, [incl, no_step, from_one],
                     f"Срез [{i}:{j}:{k}] берёт индексы от {i} до {j - 1} с шагом {k}; правая граница не входит.")
    if level == 3:
        words = rng.sample(["apple", "avocado", "banana", "blueberry", "cherry", "cranberry", "kiwi", "lemon",
                            "lime", "mango", "melon", "plum", "pear", "peach"], k=rng.randint(5, 7))
        text = " ".join(words)
        code = (f'words = "{text}".split()\ncounts = {{}}\nfor w in words:\n'
                f"    counts[w[0]] = counts.get(w[0], 0) + len(w)\nprint(max(counts.values()))")
        by_count: dict[str, int] = {}
        for w in words:
            by_count[w[0]] = by_count.get(w[0], 0) + 1
        return _item(rng, code, [max(len(w) for w in words), max(by_count.values()), sum(len(w) for w in words)],
                     "Словарь группирует слова по первой букве и суммирует длины; max берёт самую большую сумму.")
    if level == 4:
        a, b, c = rng.sample(range(2, 20), 3)
        code = (f"def push(x, acc=[]):\n    acc.append(x)\n    return sum(acc)\n\n"
                f"push({a})\npush({b})\nprint(push({c}))")
        return _item(rng, code, [c, b + c, a + c],
                     "Значение по умолчанию [] создаётся один раз при определении функции, "
                     "поэтому список копится между вызовами.")
    # level 5: late binding of closures or an exhausted generator
    if rng.random() < 0.5:
        n, k = rng.randint(3, 6), rng.randint(2, 7)
        code = f"fs = [lambda x: x * i for i in range({n})]\nprint(sum(f({k}) for f in fs))"
        return _item(rng, code, [k * sum(range(n)), k * n, k * sum(range(1, n + 1))],
                     f"Лямбды замыкают переменную i, а не её значение: к моменту вызова i = {n - 1}.", spread=9)
    n, m = rng.randint(4, 8), rng.randint(2, 3)
    code = (f"gen = (x * x for x in range({n}))\nfirst = sum(gen)\nsecond = sum(gen)\n"
            f"print(first * {m} + second)")
    total = sum(x * x for x in range(n))
    return _item(rng, code, [total * m + total, total * (m + 1) + 1, total * m - 1],
                 "Генератор одноразовый: после первого sum он исчерпан, второй sum даёт 0.", spread=9)


FAMILY = Family(
    id="py_eval", title="Python: вывод программы", topic="python", kind="code",
    specs=frozenset({"backend", "fullstack", "ml", "devops", "security", "embedded"}),
    skills=("Python",), generate=generate, a=1.5,
)
