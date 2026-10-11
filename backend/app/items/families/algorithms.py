"""Algorithms: count operations of a loop nest, and shortest paths in a small graph."""
from __future__ import annotations

import heapq
import math
import random
from collections import deque

from app.items import Family, Item, near_int, options_with
from app.items.families.langs import LANGUAGES, fib_program, loop_program
from app.items.families.python_code import run_python


def _count_item(rng, code, distractors, explanation, lang: str = "python", shown: str | None = None) -> Item:
    """`code` is the Python program the answer is computed from; `shown` is the same program in `lang`."""
    answer = run_python(code)
    options, correct = options_with(rng, answer, distractors, near_int(rng, int(answer), 4))
    shown = shown or code
    runner = {"python": "python", "javascript": "node"}.get(lang, lang)
    return Item(stem="Сколько раз увеличится count? Программа выводит итоговое значение.", code=shown,
                language=lang, options=options, correct=correct, explanation=explanation,
                verify={"runner": runner, "code": shown, "expect": answer})


def _loop(rng, lang, kind, params, distractors, explanation) -> Item:
    return _count_item(rng, loop_program("python", kind, params), distractors, explanation, lang,
                       loop_program(lang, kind, params))


def ops_generate(rng: random.Random, level: int, spec: str, lang: str = "python") -> Item:
    if lang not in LANGUAGES:
        lang = "python"
    if level == 1:
        a, b, s = rng.randint(0, 5), rng.randint(20, 40), rng.randint(3, 6)
        return _loop(rng, lang, "range", {"a": a, "b": b, "s": s},
                     [(b - a) // s, (b - a) // s + 1 + (1 if (b - a) % s == 0 else 0), b - a],
                     "Цикл от a до b с шагом s выполняется ceil((b − a) / s) раз; b не входит.")
    if level == 2:
        n = rng.randint(6, 300)  # wide range: a few dozen variants repeat across 20 leaked sessions
        kind = "tri_lt" if rng.random() < 0.5 else "tri_ge"
        return _loop(rng, lang, kind, {"n": n}, [n * n, n * (n - 1), n * (n + 1) // 2 + n],
                     "Внутренний цикл зависит от i: сумма арифметической прогрессии, порядка n²/2.")
    if level == 3:
        n = rng.randint(40, 1000)
        d = rng.choice([2, 3])
        return _loop(rng, lang, "halve", {"n": n, "d": d},
                     [round(math.log(n, d)) + 1, n // d, int(math.log2(n)) + (d == 3) * 2],
                     f"Каждый шаг делит i на {d}: число шагов — логарифм n по основанию {d} (с округлением вниз).")
    if level == 4:
        n, k = rng.randint(5, 60), rng.randint(2, 7)
        return _loop(rng, lang, "pairs", {"n": n, "k": k}, [n * n // k, n * n // k + 1, (n // k) * n],
                     "Нужно точно посчитать пары (i, j) с суммой, кратной k; оценка n²/k даёт только порядок.")
    n = rng.randint(5, 14)
    if rng.random() < 0.5 or lang != "python":
        fib = [0, 1]
        for _ in range(n + 2):
            fib.append(fib[-1] + fib[-2])
        return _count_item(rng, fib_program("python", n), [fib[n], 2 ** n, 2 * n - 1],
                           "Число вызовов наивной рекурсии Фибоначчи C(n) = C(n−1) + C(n−2) + 1 = 2·F(n+1) − 1.",
                           lang, fib_program(lang, n))
    code = ("count = 0\nmemo = {}\n\ndef f(n):\n    global count\n    count += 1\n    if n in memo:\n"
            "        return memo[n]\n    memo[n] = n if n < 2 else f(n - 1) + f(n - 2)\n    return memo[n]\n\n"
            f"f({n})\nprint(count)")
    return _count_item(rng, code, [n + 1, n, 2 ** n],
                       "С мемоизацией каждое n считается один раз, но f(n−2) ещё раз вызывается из кэша: 2n − 1 вызов.")


def _graph(rng: random.Random, nodes: int, extra: int, weighted: bool):
    labels = [chr(ord("A") + i) for i in range(nodes)]
    edges = set()
    order = labels[:]
    rng.shuffle(order)
    for i in range(1, nodes):           # a random spanning tree keeps the graph connected
        u, v = order[i], order[rng.randrange(i)]
        edges.add(tuple(sorted((u, v))))
    while len(edges) < nodes - 1 + extra:
        u, v = rng.sample(labels, 2)
        edges.add(tuple(sorted((u, v))))
    return labels, [(u, v, rng.randint(1, 9) if weighted else 1) for u, v in sorted(edges)]


def _dist(labels, edges, src):
    adj = {x: [] for x in labels}
    for u, v, w in edges:
        adj[u].append((v, w))
        adj[v].append((u, w))
    dist = {src: 0}
    heap = [(0, src)]
    while heap:
        d, u = heapq.heappop(heap)
        if d > dist[u]:
            continue
        for v, w in adj[u]:
            if d + w < dist.get(v, 10 ** 9):
                dist[v] = d + w
                heapq.heappush(heap, (d + w, v))
    return dist


def _hops(labels, edges, src):
    adj = {x: [] for x in labels}
    for u, v, _ in edges:
        adj[u].append(v)
        adj[v].append(u)
    seen = {src: 0}
    q = deque([src])
    while q:
        u = q.popleft()
        for v in adj[u]:
            if v not in seen:
                seen[v] = seen[u] + 1
                q.append(v)
    return seen


def graph_generate(rng: random.Random, level: int, spec: str) -> Item:
    weighted = level >= 4
    nodes = {1: 5, 2: 6, 3: 8, 4: 6, 5: 8}[level]
    for _ in range(50):
        labels, edges = _graph(rng, nodes, extra=level + 1, weighted=weighted)
        src, dst = rng.sample(labels, 2)
        dist = _dist(labels, edges, src)[dst]
        hops = _hops(labels, edges, src)[dst]
        if dist >= 2 and (not weighted or dist != hops):
            break
    shown = "\n".join(f"{u} — {v}" + (f"  (вес {w})" if weighted else "") for u, v, w in edges)
    if weighted:
        stem = f"Неориентированный граф с весами:\n{shown}\n\nДлина кратчайшего пути из {src} в {dst}?"
        wrong = [hops, dist + 1, dist + 2]
        why = "Веса разные, поэтому нужен алгоритм Дейкстры: путь с меньшим числом рёбер не обязательно короче."
    else:
        stem = f"Неориентированный граф:\n{shown}\n\nСколько рёбер в кратчайшем пути из {src} в {dst}?"
        wrong = [dist + 1, dist - 1, len(labels) - 1]
        why = "Поиск в ширину (BFS) находит путь с минимальным числом рёбер."
    options, correct = options_with(rng, dist, wrong, near_int(rng, dist, 3))
    return Item(stem=stem, options=options, correct=correct, explanation=why,
                verify={"runner": "graph", "edges": edges, "src": src, "dst": dst, "weighted": weighted,
                        "expect": str(dist)})


OPS = Family(
    id="algo_ops", title="Алгоритмы: подсчёт операций", topic="algorithms", kind="code",
    specs=frozenset({"backend", "fullstack", "frontend", "ml", "devops", "embedded", "mobile", "security"}),
    skills=("Algorithms",), generate=ops_generate, a=1.4, languages=LANGUAGES,
)
GRAPH = Family(
    id="algo_graph", title="Алгоритмы: кратчайший путь", topic="algorithms", kind="code",
    specs=frozenset({"backend", "fullstack", "frontend", "ml", "embedded", "mobile"}),
    skills=("Algorithms",), generate=graph_generate, a=1.3,
)
