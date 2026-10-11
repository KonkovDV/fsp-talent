"""Re-run the stored answer key of generated items in real interpreters and count the matches.

The generators compute the right answer in-process. This report runs the same snippet, query or command
again in a separate process (Python, Node.js, SQLite, bash, Go, Java when installed) and counts how many
stored keys survive. A missing interpreter is reported as "not checked", never as a match.

    python -m app.validation.key_check --variants 20
"""
from __future__ import annotations

import argparse
import ipaddress  # noqa: F401 - used by eval of verify expressions
import os
import random
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field

from app.items.registry import FAMILIES

TOOLS = {"node": "node", "go": "go", "java": "java", "bash": "bash"}
# Kotlin and C# need a JDK compiler or the .NET SDK and minutes per run; the unit test covers them in CI.
SLOW = ("kotlin", "csharp")
SKIP_RUNNERS = ("formula", "graph")


class NotAvailable(Exception):
    pass


def run(verify: dict) -> str:
    """Run one verify block independently and return its printed answer."""
    runner = verify["runner"]
    if runner == "python":
        out = subprocess.run([sys.executable, "-c", verify["code"]], capture_output=True, text=True, timeout=20)
    elif runner in ("node", "bash"):
        binary = shutil.which(TOOLS[runner])
        if not binary:
            raise NotAvailable(runner)
        with tempfile.TemporaryDirectory() as tmp:
            flag = "-e" if runner == "node" else "-c"
            out = subprocess.run([binary, flag, verify["code"]], capture_output=True, text=True, timeout=20, cwd=tmp)
        text = out.stdout.strip()
        if out.returncode != 0:
            return f"<exit {out.returncode}>"
        return " ".join(text.splitlines()) if verify.get("join_lines") else text
    elif runner in ("go", "java"):
        binary = shutil.which(TOOLS[runner])
        if not binary:
            raise NotAvailable(runner)
        with tempfile.TemporaryDirectory() as tmp:
            path = os.path.join(tmp, "main.go" if runner == "go" else "Main.java")
            with open(path, "w", encoding="utf-8") as fh:
                fh.write(verify["code"])
            cmd = [binary, "run", path] if runner == "go" else [binary, path]
            out = subprocess.run(cmd, capture_output=True, text=True, timeout=180, cwd=tmp)
    elif runner == "sqlite":
        con = sqlite3.connect(":memory:")
        try:
            con.executescript(verify["schema"])
            return str(con.execute(verify["query"]).fetchone()[0])
        finally:
            con.close()
    elif runner == "ipaddress":
        return str(eval(verify["expr"]))  # noqa: S307 - our own generated expression
    else:
        raise NotAvailable(runner)
    if out.returncode != 0:
        return f"<exit {out.returncode}>"
    return out.stdout.strip()


def matches(verify: dict, got: str) -> bool:
    if "expect_mode" in verify:
        try:
            return int(got, 8) == verify["expect_mode"]
        except ValueError:
            return False
    return got == verify["expect"]


@dataclass
class Tally:
    checked: int = 0
    matched: int = 0
    not_checked: int = 0
    runners: set[str] = field(default_factory=set)
    misses: list[str] = field(default_factory=list)


def check(variants: int = 20, seed: int = 2026, families: list[str] | None = None) -> dict[str, Tally]:
    """For each code family and level, generate `variants` items and re-run every key."""
    result: dict[str, Tally] = {}
    for fid in sorted(families or FAMILIES):
        family = FAMILIES[fid]
        if family.kind != "code":
            continue
        tally = result.setdefault(fid, Tally())
        langs = [lang for lang in family.languages if lang not in SLOW] or ["python"]
        for level in family.levels:
            spec = next((s for s in sorted(family.specs) if family.available(s, level)), None)
            if spec is None:
                continue
            for index in range(variants):
                lang = langs[index % len(langs)]
                rng = random.Random(seed * 1000 + level * 100 + index)
                kwargs = {"lang": lang} if len(family.languages) > 1 else {}
                item = family.generate(rng, level, spec, **kwargs)
                verify = item.verify
                if not verify or verify["runner"] in SKIP_RUNNERS:
                    continue
                tally.runners.add(verify["runner"])
                try:
                    got = run(verify)
                except NotAvailable:
                    tally.not_checked += 1
                    continue
                tally.checked += 1
                if matches(verify, got):
                    tally.matched += 1
                elif len(tally.misses) < 3:
                    tally.misses.append(f"level {level}: got {got!r}, key {verify.get('expect')!r}")
    return result


def markdown(result: dict[str, Tally], variants: int, seed: int) -> str:
    lines = [
        f"Ключи заданий с кодом: по {variants} вариантов на уровень, зерно {seed}. "
        "Каждый вариант заново исполнен отдельным процессом, ответ сверен с сохранённым ключом.",
        "",
        "| Семейство | Исполнитель | Исполнено | Совпало с ключом | Не проверено (нет исполнителя) |",
        "|---|---|---|---|---|",
    ]
    for fid, t in result.items():
        if not t.runners:
            continue
        lines.append(f"| {fid} | {', '.join(sorted(t.runners))} | {t.checked} | {t.matched} | {t.not_checked} |")
    checked = sum(t.checked for t in result.values())
    matched = sum(t.matched for t in result.values())
    missing = sum(t.not_checked for t in result.values())
    lines += ["", f"Итого: исполнено {checked}, совпало с ключом {matched}, не проверено {missing}."]
    for fid, t in result.items():
        for miss in t.misses:
            lines.append(f"- расхождение {fid}, {miss}")
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--variants", type=int, default=20)
    parser.add_argument("--seed", type=int, default=2026)
    args = parser.parse_args()
    result = check(args.variants, args.seed)
    print(markdown(result, args.variants, args.seed))
    if any(t.matched != t.checked for t in result.values()):
        sys.exit(1)


if __name__ == "__main__":
    main()
