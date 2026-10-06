"""Every generated item has four distinct options, and its stored answer survives an independent re-run.

Python snippets run in a separate interpreter, JavaScript in Node.js, SQL in a fresh SQLite database. The
generators compute answers in-process; this test makes sure that what the candidate sees and what is scored
cannot drift apart.
"""
import ipaddress  # noqa: F401 - used by eval of verify expressions
import os
import random
import shutil
import sqlite3
import subprocess
import sys
import tempfile

import pytest

from app.items.registry import BLUEPRINTS, CONCEPT_MAX_SHARE, FAMILIES, families_for

NODE = shutil.which("node")
GO = shutil.which("go")
JAVA = shutil.which("java")
KOTLIN = shutil.which("kotlinc")
DOTNET = shutil.which("dotnet")
SEEDS = range(4)
_CSPROJ = """<Project Sdk="Microsoft.NET.Sdk">
  <PropertyGroup>
    <OutputType>Exe</OutputType>
    <TargetFramework>net8.0</TargetFramework>
    <ImplicitUsings>enable</ImplicitUsings>
    <Nullable>disable</Nullable>
  </PropertyGroup>
</Project>
"""


def _require(binary: str | None, name: str) -> None:
    """Skip a language the machine does not have. In CI a missing compiler is a failure."""
    if binary:
        return
    if os.environ.get("CI"):
        pytest.fail(f"{name} must be installed when CI is set")
    pytest.skip(f"{name} is not installed")


def _cases():
    for spec in BLUEPRINTS:
        for family in families_for(spec):
            for level in family.levels:
                if family.available(spec, level):
                    yield spec, family.id, level


CASES = sorted(set(_cases()))


@pytest.mark.parametrize("spec,family_id,level", CASES)
def test_options_are_distinct_and_answer_is_present(spec, family_id, level):
    family = FAMILIES[family_id]
    for seed in range(60):
        item = family.generate(random.Random(seed * 101 + level), level, spec)
        assert len(item.options) == 4 and len(set(item.options)) == 4, item.options
        assert 0 <= item.correct < 4
        if item.verify and "expect" in item.verify and not item.verify.get("predicate"):
            assert item.options[item.correct] == item.verify["expect"], (item.options, item.verify)


def _run(verify: dict) -> str:
    runner = verify["runner"]
    if runner == "python":
        out = subprocess.run([sys.executable, "-c", verify["code"]], capture_output=True, text=True, timeout=10)
        assert out.returncode == 0, out.stderr
        return out.stdout.strip()
    if runner == "node":
        out = subprocess.run([NODE, "-e", verify["code"]], capture_output=True, text=True, timeout=10)
        assert out.returncode == 0, out.stderr
        text = out.stdout.strip()
        return " ".join(text.splitlines()) if verify.get("join_lines") else text
    if runner in ("go", "java", "kotlin", "csharp"):
        with tempfile.TemporaryDirectory() as tmp:
            if runner == "kotlin":
                path = os.path.join(tmp, "Main.kt")
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(verify["code"])
                jar = os.path.join(tmp, "app.jar")
                compiled = subprocess.run([KOTLIN, path, "-include-runtime", "-d", jar],
                                          capture_output=True, text=True, timeout=120)
                assert compiled.returncode == 0, compiled.stderr
                out = subprocess.run([JAVA, "-jar", jar], capture_output=True, text=True, timeout=30)
            elif runner == "csharp":
                with open(os.path.join(tmp, "App.csproj"), "w", encoding="utf-8") as fh:
                    fh.write(_CSPROJ)
                with open(os.path.join(tmp, "Program.cs"), "w", encoding="utf-8") as fh:
                    fh.write(verify["code"])
                env = {**os.environ, "DOTNET_NOLOGO": "1", "DOTNET_CLI_TELEMETRY_OPTOUT": "1"}
                out = subprocess.run([DOTNET, "run", "--nologo", "-v", "q"],
                                     capture_output=True, text=True, timeout=180, cwd=tmp, env=env)
            else:
                name = "main.go" if runner == "go" else "Main.java"
                path = os.path.join(tmp, name)
                with open(path, "w", encoding="utf-8") as fh:
                    fh.write(verify["code"])
                cmd = [GO, "run", path] if runner == "go" else [JAVA, path]
                out = subprocess.run(cmd, capture_output=True, text=True, timeout=120, cwd=tmp)
            assert out.returncode == 0, out.stderr
            return out.stdout.strip()
    if runner == "sqlite":
        con = sqlite3.connect(":memory:")
        con.executescript(verify["schema"])
        value = con.execute(verify["query"]).fetchone()[0]
        con.close()
        return str(value)
    if runner == "ipaddress":
        return str(eval(verify["expr"]))  # noqa: S307 - our own expression
    raise AssertionError(runner)


@pytest.mark.parametrize("family_id", sorted(FAMILIES))
def test_stored_answer_matches_an_independent_run(family_id):
    family = FAMILIES[family_id]
    checked = 0
    for spec in sorted(family.specs):
        for level in family.levels:
            if not family.available(spec, level):
                continue
            for seed in SEEDS:
                item = family.generate(random.Random(seed), level, spec)
                verify = item.verify
                if not verify or verify["runner"] in ("formula", "graph"):
                    continue
                if verify["runner"] == "node":
                    _require(NODE, "node")
                got = _run(verify)
                if "expect_mode" in verify:
                    assert int(got, 8) == verify["expect_mode"]
                else:
                    assert got == verify["expect"], (family_id, level, item.code, got, verify["expect"])
                checked += 1
        break   # answers do not depend on the specialization; one spec is enough
    if family.kind == "code" and family.id != "algo_graph":   # graphs: see the Bellman-Ford test below
        assert checked > 0


def test_graph_answers_match_networkx_free_reference():
    family = FAMILIES["algo_graph"]
    for level in family.levels:
        for seed in range(30):
            item = family.generate(random.Random(seed), level, "backend")
            v = item.verify
            # Bellman-Ford as an independent reference for both weighted and unweighted graphs.
            dist = {v["src"]: 0}
            for _ in range(20):
                for a, b, w in v["edges"]:
                    w = w if v["weighted"] else 1
                    for x, y in ((a, b), (b, a)):
                        if x in dist and dist[x] + w < dist.get(y, 10 ** 9):
                            dist[y] = dist[x] + w
            assert str(dist[v["dst"]]) == v["expect"] == item.options[item.correct]


def test_every_specialization_has_its_own_families_and_no_foreign_ones():
    for spec, topics in BLUEPRINTS.items():
        assert abs(sum(topics.values()) - 1.0) < 1e-9, spec
        fams = families_for(spec)
        assert {f.topic for f in fams} == set(topics), spec
        assert all(spec in f.specs for f in fams)
        code = [f for f in fams if f.kind == "code"]
        assert len(code) >= 3, f"{spec}: too few computed families"
        assert topics.get("concept", 0) <= CONCEPT_MAX_SHARE


def test_items_are_practically_unique():
    """A leaked item says little about the next session: 200 draws of one level give 120+ distinct items."""
    for fid in ("py_eval", "sql_query", "algo_ops", "js_eval", "net_ipv4", "ml_metrics", "emb_bits"):
        family = FAMILIES[fid]
        spec = sorted(family.specs)[0]
        stems = {(item.stem, item.code) for item in
                 (family.generate(random.Random(s), 3, spec) for s in range(200))}
        assert len(stems) >= 120, (fid, len(stems))


@pytest.mark.parametrize("lang", ["python", "javascript", "go", "java", "kotlin", "csharp"])
def test_counting_programs_agree_across_languages(lang):
    """The candidate may read loops in another language; the answer must be the same program's answer."""
    tools = {"javascript": (NODE, "node"), "go": (GO, "go"), "java": (JAVA, "java"),
             "kotlin": (KOTLIN, "kotlinc"), "csharp": (DOTNET, "dotnet")}
    if lang in tools:
        _require(*tools[lang])
    if lang == "kotlin":
        _require(JAVA, "java")
    family = FAMILIES["algo_ops"]
    for level in family.levels:
        item = family.generate(random.Random(level * 7), level, "backend", lang=lang)
        assert item.language == lang
        assert _run(item.verify) == item.options[item.correct], (lang, level, item.code)


def test_kotlin_and_csharp_show_the_python_answer():
    """The scored number comes from the Python program; the other languages only change the source shown."""
    family = FAMILIES["algo_ops"]
    for level in family.levels:
        base = family.generate(random.Random(level * 7), level, "backend", lang="python")
        expect = base.options[base.correct]
        for lang, marker in (("kotlin", "println"), ("csharp", "Console.WriteLine")):
            item = family.generate(random.Random(level * 7), level, "backend", lang=lang)
            assert item.language == lang and marker in item.code
            assert item.options[item.correct] == expect
            assert item.verify["expect"] == expect and item.verify["runner"] == lang
