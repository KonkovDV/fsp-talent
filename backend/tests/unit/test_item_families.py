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
    if runner == "bash":
        _require(shutil.which("bash"), "bash")
        with tempfile.TemporaryDirectory() as tmp:
            out = subprocess.run(["bash", "-c", verify["code"]], capture_output=True, text=True, timeout=10, cwd=tmp)
        assert out.returncode == 0, out.stderr
        return out.stdout.strip()
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


BASH = shutil.which("bash")


def _run_bash(script: str) -> str:
    with tempfile.TemporaryDirectory() as tmp:
        out = subprocess.run([BASH, "-c", script], capture_output=True, text=True, timeout=10, cwd=tmp)
    return out.stdout.strip()


@pytest.mark.parametrize("family_id", ["docker_ops", "k8s_ops", "linux_shell"])
@pytest.mark.parametrize("level", [1, 2, 3, 4, 5])
def test_devops_family_is_deterministic_typed_and_varied(family_id, level):
    """Same seed, same item; 60 seeds give 30+ different items; the key is a whole number typed by the candidate."""
    from app.items import typed_answer

    family = FAMILIES[family_id]
    first = family.generate(random.Random(11), level, "devops")
    again = family.generate(random.Random(11), level, "devops")
    assert first == again
    seen = set()
    for seed in range(60):
        item = family.generate(random.Random(seed), level, "devops")
        assert typed_answer(family.kind, item) == item.options[item.correct], (family_id, level, item.options)
        assert int(item.options[item.correct]) >= 0
        seen.add((item.stem, item.code))
    assert len(seen) >= 30, (family_id, level, len(seen))


def _k8s_reference(p: dict) -> int:
    """Kubernetes rules written out again, apart from the generator."""
    import math
    kind = p["kind"]
    if kind == "requests":
        return p["replicas"] * (p["cpu"] + p["sidecar"])
    if kind == "rolling":
        r = p["replicas"]
        if p["ask_top"]:
            s = p["surge"]
            return r + (-(-r * int(s[:-1]) // 100) if s.endswith("%") else int(s))
        u = p["unavailable"]
        return r - (r * int(u[:-1]) // 100 if u.endswith("%") else int(u))
    if kind == "hpa":
        want = math.ceil(p["current"] * p["metric"] / p["target"])
        return min(p["hi"], max(p["lo"], want))
    if kind == "schedule":
        placed, left = 0, p["replicas"]
        for cpu_free, mem_free in p["nodes"]:      # greedy placement one pod at a time
            while left and cpu_free >= p["cpu"] and mem_free >= p["mem"]:
                cpu_free, mem_free, left, placed = cpu_free - p["cpu"], mem_free - p["mem"], left - 1, placed + 1
        return left
    raise AssertionError(kind)


def _docker_reference(p: dict, item) -> int:
    kind = p["kind"]
    if kind == "port":
        host, inside = p["spec"].split(":")[-2:]
        assert f"{host}:{inside}" in item.code
        return int(host if p["ask_host"] else inside)
    if kind == "cache":
        dirty = False
        rebuilt = 0
        for text, takes in p["steps"]:
            if takes and not dirty:
                if takes == ["*"]:
                    dirty = any(c not in p["ignored"] for c in p["changed"])
                else:
                    dirty = bool(set(takes) & set(p["changed"]))
            if dirty and text.startswith("RUN"):
                rebuilt += 1
            assert text in item.code
        return rebuilt
    if kind == "multistage":
        return p["final"] + p["extra"] + p["artifact"]
    if kind == "layers":
        return p["base"] + p["unpacked"] + (0 if p["together"] else p["archive"])
    raise AssertionError(kind)


@pytest.mark.parametrize("family_id", ["docker_ops", "k8s_ops"])
def test_container_keys_match_a_separate_reference(family_id):
    family = FAMILIES[family_id]
    for level in family.levels:
        for seed in range(80):
            item = family.generate(random.Random(seed), level, "devops")
            p = item.verify["params"]
            ref = _k8s_reference(p) if family_id == "k8s_ops" else _docker_reference(p, item)
            assert str(ref) == item.options[item.correct] == item.verify["expect"], (level, seed, p)


def test_cron_key_matches_a_minute_by_minute_walk():
    family = FAMILIES["linux_shell"]

    def fires(field: str, value: int, top: int) -> bool:
        allowed = set()
        for part in field.split(","):
            rng_part, _, step = part.partition("/")
            lo, hi = (0, top) if rng_part == "*" else (
                tuple(map(int, rng_part.split("-"))) if "-" in rng_part else (int(rng_part), int(rng_part)))
            allowed.update(range(lo, hi + 1, int(step or 1)))
        return value in allowed

    for seed in range(120):
        item = family.generate(random.Random(seed), 4, "devops")
        p = item.verify["params"]
        assert f"{p['minute']} {p['hour']} * * *" in item.code
        t, waited = p["now"], 0
        while True:
            t, waited = (t + 1) % 1440, waited + 1
            if fires(p["minute"], t % 60, 59) and fires(p["hour"], t // 60, 23):
                break
        assert str(waited) == item.options[item.correct], (p, waited)


@pytest.mark.parametrize("level", [1, 2, 3, 5])
def test_shell_keys_match_bash(level):
    """grep, chmod, the text pipeline and exit codes: the script itself runs in bash and prints the key."""
    _require(BASH, "bash")
    family = FAMILIES["linux_shell"]
    for seed in range(25):
        item = family.generate(random.Random(seed), level, "devops")
        assert item.verify["runner"] == "bash"
        assert _run_bash(item.code) == item.options[item.correct], (level, seed, item.code)
