"""JavaScript: what the snippet logs. Answers follow JS semantics; unit tests re-run each snippet in Node.js."""
from __future__ import annotations

import itertools
import random

from app.items import Family, Item, near_int, options_with


def _item(rng, code, answer, distractors, why, numeric=True) -> Item:
    filler = near_int(rng, int(answer), 5) if numeric else None
    options, correct = options_with(rng, answer, distractors, filler)
    return Item(stem="Что выведет console.log?", code=code, language="javascript", options=options,
                correct=correct, explanation=why, verify={"runner": "node", "code": code, "expect": str(answer)})


def generate(rng: random.Random, level: int, spec: str) -> Item:
    if level == 1:
        xs = rng.sample(range(1, 15), 5)
        k, t = rng.randint(2, 4), rng.randint(10, 30)
        code = f"const xs = {xs};\nconsole.log(xs.map(v => v * {k}).filter(v => v > {t}).length);"
        ans = sum(1 for v in xs if v * k > t)
        return _item(rng, code, ans, [sum(1 for v in xs if v > t), sum(1 for v in xs if v * k >= t), len(xs)],
                     "map умножает каждый элемент, filter оставляет только большие порога, length — их число.")
    if level == 2:
        x, y, z = rng.randint(2, 9), rng.randint(2, 9), rng.randint(2, 9)
        if rng.random() < 0.5:
            code = f'console.log("{x}" + {y} + {z});'
            ans, wrong = f"{x}{y}{z}", [x + y + z, f"{x}{y + z}", f"{x + y}{z}"]
            why = "Сложение идёт слева направо: строка + число даёт строку, дальше только склейка."
        else:
            code = f'console.log({y} + {z} + "{x}");'
            ans, wrong = f"{y + z}{x}", [f"{y}{z}{x}", y + z + x, f"{y}{z + x}"]
            why = "Сначала складываются два числа, потом результат склеивается со строкой."
        return _item(rng, code, ans, wrong, why, numeric=False)
    if level == 3:
        n, k, start = rng.randint(3, 6), rng.randint(2, 5), rng.randint(0, 9)
        kw = rng.choice(["var", "let"])
        code = (f"const fs = [];\nfor ({kw} i = {start}; i < {start + n}; i++) fs.push(() => i * {k});\n"
                "console.log(fs.reduce((s, f) => s + f(), 0));")
        with_var, with_let = n * (start + n) * k, k * sum(range(start, start + n))
        ans = with_var if kw == "var" else with_let
        other = with_let if kw == "var" else with_var
        why = ("var — одна переменная на весь цикл, к моменту вызова i уже равна конечному значению." if kw == "var"
               else "let создаёт новую привязку i на каждой итерации.")
        return _item(rng, code, ans, [other, n * k, (start + n - 1) * n * k], why)
    if level == 4:
        labels = rng.sample("ABCDEFGH", 4)
        kinds = ["sync", "timeout", "micro", "sync"]
        rng.shuffle(kinds)
        if "sync" not in kinds[:1]:
            kinds[0], kinds[kinds.index("sync")] = "sync", kinds[0]
        lines = []
        for lab, kind in zip(labels, kinds, strict=True):
            if kind == "sync":
                lines.append(f'console.log("{lab}");')
            elif kind == "timeout":
                lines.append(f'setTimeout(() => console.log("{lab}"), 0);')
            else:
                lines.append(f'Promise.resolve().then(() => console.log("{lab}"));')
        order = ([lab for lab, k in zip(labels, kinds, strict=True) if k == "sync"]
                 + [lab for lab, k in zip(labels, kinds, strict=True) if k == "micro"]
                 + [lab for lab, k in zip(labels, kinds, strict=True) if k == "timeout"])
        ans = " ".join(order)
        wrong = [" ".join(labels)] + [" ".join(p) for p in itertools.permutations(order) if " ".join(p) != ans]
        rng.shuffle(wrong)
        wrong.insert(0, " ".join(labels))
        return Item(stem="В каком порядке появятся строки в консоли?", code="\n".join(lines), language="javascript",
                    options=(opts := options_with(rng, ans, wrong))[0], correct=opts[1],
                    explanation="Сначала синхронный код, затем микрозадачи (then), затем макрозадачи (setTimeout).",
                    verify={"runner": "node", "code": "\n".join(lines), "expect": ans, "join_lines": True})
    x, y, z, w = rng.sample(range(1, 20), 4)
    code = (f"const base = {{ a: {x}, b: {y} }};\nconst o = {{ ...base, a: {z}, ...{{ b: {w} }} }};\n"
            "const { a, b, c = a + b } = o;\nconsole.log(c);")
    return _item(rng, code, z + w, [x + y, z + y, x + w],
                 "Поздние свойства в литерале перезаписывают ранние; значение по умолчанию c вычисляется из a и b.")


FAMILY = Family(
    id="js_eval", title="JavaScript: вывод программы", topic="javascript", kind="code",
    specs=frozenset({"frontend", "fullstack", "mobile"}), skills=("JavaScript",),
    generate=generate, a=1.5,
)
