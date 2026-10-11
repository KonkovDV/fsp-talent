"""DevOps: Linux and shell. Answers are whole numbers; unit tests run every script in bash and compare.

grep -c over a log, symbolic chmod, a text pipeline (cut | sort | uniq), minutes until the next cron run, and
the exit status of a pipeline with and without pipefail.
"""
from __future__ import annotations

import random

from app.items import Family, Item, options_with

LEVELS_LOG = ("INFO", "WARN", "ERROR", "DEBUG")
PATHS = ("/api/users", "/api/orders", "/health", "/login", "/api/items")
USERS = ("alice", "bob", "carol", "dave", "erin", "frank", "grace", "heidi")


def _item(rng: random.Random, stem: str, script: str, ans: int, wrong: list[int], why: str, spread: int = 3,
          language: str = "bash", verify: dict | None = None) -> Item:
    options, correct = options_with(rng, ans, [w for w in wrong if w != ans and w >= 0],
                                    lambda: max(0, ans + rng.choice([-1, 1]) * rng.randint(1, max(3, spread))))
    return Item(stem=stem, code=script, language=language, options=options, correct=correct, explanation=why,
                verify=verify or {"runner": "bash", "code": script, "expect": str(ans)})


def _heredoc(lines: list[str], name: str) -> str:
    return f"cat > {name} <<'EOF'\n" + "\n".join(lines) + "\nEOF\n"


def _grep_count(rng: random.Random) -> Item:
    rows = []
    for i in range(rng.randint(7, 11)):
        lvl = rng.choice(LEVELS_LOG)
        rows.append(f"12:{i:02d}:0{rng.randint(0, 9)} {lvl} {rng.choice(PATHS)} {rng.choice([200, 201, 404, 500])}")
    word = rng.choice(["ERROR", "WARN", "500", "/api/"])
    inverted = rng.random() < 0.3
    flag = "-vc" if inverted else "-c"
    script = _heredoc(rows, "app.log") + f"grep {flag} '{word}' app.log"
    hits = sum(word in r for r in rows)
    ans = len(rows) - hits if inverted else hits
    return _item(rng, "Что выведет последняя команда?", script, ans,
                 [len(rows) - ans, ans + 1, len(rows)],
                 "grep -c считает строки с совпадением, а не сами совпадения; -v берёт строки без совпадения.")


def _apply_chmod(mode: int, spec: str) -> int:
    bits = {"r": 4, "w": 2, "x": 1}
    shifts = {"u": 6, "g": 3, "o": 0}
    for clause in spec.split(","):
        who, op, perms = clause[0], clause[1], clause[2:]
        targets = "ugo" if who == "a" else who
        value = sum(bits[p] for p in perms)
        for t in targets:
            mask = value << shifts[t]
            if op == "+":
                mode |= mask
            elif op == "-":
                mode &= ~mask
            else:
                mode = (mode & ~(7 << shifts[t])) | mask
    return mode


def _chmod(rng: random.Random) -> Item:
    start = rng.choice([0o644, 0o600, 0o640, 0o755, 0o750, 0o664, 0o700])
    clauses = []
    for who in rng.sample(["u", "g", "o"], k=rng.randint(1, 2)):
        op = rng.choice("+-=")
        perms = "".join(sorted(rng.sample("rwx", k=rng.randint(1, 2)), key="rwx".index))
        if who == "u" and op in "-=":
            op, perms = "+", "x"      # keep the owner able to read the file
        clauses.append(f"{who}{op}{perms}")
    spec = ",".join(clauses)
    mode = _apply_chmod(start, spec)
    ans = int(f"{mode:o}")
    script = f"touch f\nchmod {start:o} f\nchmod {spec} f\nstat -c %a f"
    naive = int(f"{start:o}")
    return _item(rng, "Что выведет stat (права в восьмеричном виде)?", script, ans,
                 [naive, int(f"{start | 0o111:o}"), int(f"{(start ^ 0o022) & 0o777:o}")],
                 "r = 4, w = 2, x = 1 для владельца (u), группы (g) и остальных (o). + добавляет биты, − убирает, "
                 "= ставит ровно указанные.", spread=10)


def _pipeline(rng: random.Random) -> Item:
    n = rng.randint(8, 12)
    rows = [f"{rng.choice(USERS[:rng.randint(3, 6)])}:{rng.choice(PATHS)}:{rng.choice([200, 404, 500])}"
            for _ in range(n)]
    field = rng.choice([1, 2, 3])
    mode = rng.choice(["uniq", "top", "nosort"])
    col = [r.split(":")[field - 1] for r in rows]
    if mode == "uniq":
        tail, ans = "sort | uniq | wc -l", len(set(col))
        why = "uniq убирает только соседние повторы, поэтому перед ним sort; wc -l считает строки."
    elif mode == "top":
        counts: dict[str, int] = {}
        for v in col:
            counts[v] = counts.get(v, 0) + 1
        tail, ans = "sort | uniq -c | sort -rn | head -1 | awk '{print $1}'", max(counts.values())
        why = "uniq -c после sort даёт число повторов каждого значения, sort -rn ставит самое частое первым."
    else:
        runs = 1 + sum(1 for a, b in zip(col, col[1:], strict=False) if a != b)
        tail, ans = "uniq | wc -l", runs
        why = "Без sort uniq склеивает только подряд идущие одинаковые строки."
    script = _heredoc(rows, "access.txt") + f"cut -d: -f{field} access.txt | {tail}"
    return _item(rng, "Что выведет последняя команда?", script, ans,
                 [len(set(col)), n, 1 + sum(1 for a, b in zip(col, col[1:], strict=False) if a != b), ans + 1],
                 why)


def cron_matches(field: str, value: int) -> bool:
    for part in field.split(","):
        step = 1
        if "/" in part:
            part, step_text = part.split("/")
            step = int(step_text)
        if part == "*":
            lo, hi = 0, 59
        elif "-" in part:
            lo, hi = map(int, part.split("-"))
        else:
            lo = hi = int(part)
            if step != 1:
                hi = 59
        if lo <= value <= hi and (value - lo) % step == 0:
            return True
    return False


def minutes_to_next(minute_field: str, hour_field: str, now: int) -> int:
    """Minutes from `now` (minutes since midnight) to the next run strictly after it."""
    for delta in range(1, 2 * 24 * 60):
        t = (now + delta) % (24 * 60)
        if cron_matches(minute_field, t % 60) and cron_matches(hour_field, t // 60):
            return delta
    raise ValueError("cron never fires")


def _cron(rng: random.Random) -> Item:
    minute = rng.choice(["*/15", "*/10", "0", "30", "5,35", "*/20", "45"])
    hour = rng.choice(["*", "9-18", "*/2", "8,20", "0-6", "*/6"])
    now = rng.randint(0, 24 * 60 - 1)
    ans = minutes_to_next(minute, hour, now)
    clock = f"{now // 60:02d}:{now % 60:02d}"
    line = f"{minute} {hour} * * * /usr/local/bin/backup.sh"
    every = minutes_to_next(minute, "*", now)
    return _item(rng, f"Строка crontab ниже. Сейчас ровно {clock}, сегодняшние запуски до этого момента уже прошли. "
                      "Через сколько минут скрипт запустится в следующий раз?", line, ans,
                 [every, ans + 60, max(1, ans - 1)],
                 "Поля: минута, час, день месяца, месяц, день недели. */n — каждое n-е значение начиная с 0, "
                 "a-b — диапазон. Запуск — когда совпали все поля.", spread=15, language="text",
                 verify={"runner": "python", "expect": str(ans), "params": {"minute": minute, "hour": hour,
                                                                            "now": now},
                         "code": _cron_check(minute, hour, now)})


def _cron_check(minute: str, hour: str, now: int) -> str:
    # Brute force over every minute with the standard cron expansion, written apart from cron_matches.
    return (f"def expand(f, top):\n    out = set()\n    for p in f.split(','):\n"
            "        base, _, step = p.partition('/')\n        step = int(step or 1)\n"
            "        if base == '*':\n            lo, hi = 0, top\n        elif '-' in base:\n"
            "            lo, hi = map(int, base.split('-'))\n        else:\n"
            "            lo = int(base); hi = top if _ else lo\n"
            "        out |= set(range(lo, hi + 1, step))\n    return out\n"
            f"m, h = expand('{minute}', 59), expand('{hour}', 23)\n"
            f"now = {now}\n"
            "print(next(d for d in range(1, 2881) if (now + d) % 60 in m and (now + d) // 60 % 24 in h))")


def _exit_status(rng: random.Random) -> Item:
    codes = [rng.choice([0, 0, 1, 2, 3, 127]) for _ in range(rng.randint(2, 3))]
    if all(c == 0 for c in codes):
        codes[rng.randrange(len(codes) - 1)] = rng.choice([1, 2, 3])
    pipefail = rng.random() < 0.6
    stages = " | ".join(f"(exit {c})" for c in codes)
    script = ("set -o pipefail\n" if pipefail else "") + f"{stages}\necho $?"
    nonzero = [c for c in codes if c]
    ans = (nonzero[-1] if nonzero else 0) if pipefail else codes[-1]
    other = codes[-1] if pipefail else (nonzero[-1] if nonzero else 0)
    return _item(rng, "Что выведет скрипт bash?", script, ans, [other, codes[0], 1, 0],
                 "$? конвейера — код последней команды. С pipefail — код самой правой команды, завершившейся "
                 "с ошибкой, или 0, если ошибок нет.", spread=2)


def generate(rng: random.Random, level: int, spec: str) -> Item:
    del spec
    return {1: _grep_count, 2: _chmod, 3: _pipeline, 4: _cron, 5: _exit_status}[level](rng)


FAMILY = Family(
    id="linux_shell", title="Linux: права, конвейеры, cron и коды выхода", topic="infra", kind="code",
    specs=frozenset({"devops"}), skills=("Linux",), generate=generate, a=1.3,
)
