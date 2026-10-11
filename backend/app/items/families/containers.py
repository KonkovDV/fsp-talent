"""DevOps: Docker images and Kubernetes workloads. Every answer is a whole number computed from the shown spec.

Docker: published ports, the build cache (a changed input rebuilds its step and every step after it, a
.dockerignore'd file changes nothing), multi-stage images and layers that a later `rm` does not shrink.
Kubernetes: requests, rolling-update bounds (maxSurge rounds up, maxUnavailable rounds down), the HPA rule
desired = ceil(current · metric / target) clamped to [min, max], and how many replicas the nodes can hold.
"""
from __future__ import annotations

import math
import random

from app.items import Family, Item, options_with

PORTS = (80, 443, 3000, 5000, 5432, 6379, 8000, 8080, 9000, 9090)
IMAGES = ("nginx", "app", "api", "web", "worker")


def _typed(rng: random.Random, stem: str, ans: int, wrong: list[int], why: str, code: str | None = None,
           language: str | None = None, check: str = "", params: dict | None = None, spread: int = 4) -> Item:
    options, correct = options_with(rng, ans, [w for w in wrong if w != ans and w >= 0],
                                    lambda: max(0, ans + rng.choice([-1, 1]) * rng.randint(1, max(3, spread))))
    return Item(stem=stem, options=options, correct=correct, explanation=why, code=code, language=language,
                verify={"runner": "python", "code": check, "expect": str(ans), "params": params or {}})


# ---------------------------------------------------------------- Docker

def _docker_port(rng: random.Random) -> Item:
    inside = rng.choice(PORTS)
    host = rng.choice([p for p in range(1025, 9999) if p != inside])
    image = rng.choice(IMAGES)
    ask_host = rng.random() < 0.5
    bind = rng.choice(["", "127.0.0.1:"])
    code = f"docker run -d -p {bind}{host}:{inside} {image}"
    if ask_host:
        stem = "Контейнер запущен так. На какой порт машины-хоста нужно идти, чтобы попасть в сервис?"
        ans, other = host, inside
    else:
        stem = "Контейнер запущен так. Какой порт должен слушать процесс внутри контейнера?"
        ans, other = inside, host
    return _typed(rng, stem, ans, [other, ans + 1, 80 if ans != 80 else 8080], code=code, language="bash",
                  why="В -p слева порт хоста (и, если указан, адрес), справа — порт внутри контейнера.",
                  check=f"spec = '{bind}{host}:{inside}'\nprint(spec.split(':')[{-2 if ask_host else -1}])",
                  params={"kind": "port", "spec": f"{bind}{host}:{inside}", "ask_host": ask_host}, spread=10)


STACKS = {
    "python": ("python:3.12-slim", ("COPY requirements.txt .", {"requirements.txt"}),
               "RUN pip install --no-cache-dir -r requirements.txt",
               ["RUN python -m compileall -q .", "RUN pytest -q", "RUN python manage.py collectstatic --noinput"],
               'CMD ["python", "app.py"]',
               ("app.py", "settings.py", "README.md", "static/site.css", "tests/test_api.py")),
    "node": ("node:20-slim", ("COPY package.json package-lock.json ./", {"package.json", "package-lock.json"}),
             "RUN npm ci", ["RUN npm run build", "RUN npm test", "RUN npm prune --omit=dev"],
             'CMD ["node", "dist/server.js"]', ("src/index.ts", "src/api.ts", "README.md", "public/logo.svg",
                                                "tests/api.test.ts")),
}


def _dockerfile(rng: random.Random) -> tuple[str, list[tuple[str, set[str] | None]], str, tuple[str, ...]]:
    base, deps_copy, install, tail, cmd, sources = STACKS[rng.choice(sorted(STACKS))]
    steps: list[tuple[str, set[str] | None]] = []
    if rng.random() < 0.5:
        steps.append(("RUN apt-get update && apt-get install -y --no-install-recommends curl", None))
    steps += [deps_copy, (install, None), ("COPY . .", {"*"})]
    steps += [(text, None) for text in rng.sample(tail, k=rng.randint(1, len(tail)))]
    return base, steps, cmd, sources


def _covers(pattern: set[str], name: str, ignored: set[str]) -> bool:
    if "*" in pattern:
        return name not in ignored
    return name in pattern


def rebuilt_runs(steps: list[tuple[str, set[str] | None]], changed: set[str], ignored: set[str]) -> int:
    """RUN instructions that miss the cache: the first COPY that takes a changed file, and every step after it."""
    for i, (_, takes) in enumerate(steps):
        if takes is not None and any(_covers(takes, name, ignored) for name in changed):
            return sum(1 for text, _ in steps[i:] if text.startswith("RUN"))
    return 0


def _docker_cache(rng: random.Random, with_ignore: bool) -> Item:
    base, steps, cmd, sources = _dockerfile(rng)
    deps = sorted(n for _, t in steps if t and "*" not in t for n in t)
    changed = set(rng.sample(list(sources) + deps, k=2 if with_ignore else 1))
    ignored: set[str] = set()
    if with_ignore:
        ignored = set(rng.sample(sources, k=2))
        if rng.random() < 0.5:
            ignored |= {n for n in changed if n in sources}
    lines = [f"FROM {base}", "WORKDIR /app"] + [text for text, _ in steps] + [cmd]
    ans = rebuilt_runs(steps, changed, ignored)
    total_runs = sum(1 for text, _ in steps if text.startswith("RUN"))
    copy_all = [t for t, _ in steps].index("COPY . .")
    after_copy_all = sum(1 for text, _ in steps[copy_all:] if text.startswith("RUN"))
    shown = ", ".join(sorted(changed))
    stem = (f"Образ уже собирался, кэш слоёв цел. Изменили только {shown}. "
            "Сколько инструкций RUN выполнится заново при следующем docker build?")
    if with_ignore:
        stem = f"В .dockerignore: {', '.join(sorted(ignored))}. " + stem
    why = ("Кэш шага сбрасывается, если изменился файл, который этот шаг копирует; после первого сброса заново "
           "выполняются все следующие шаги. Файл из .dockerignore в контекст сборки не попадает и кэш не трогает.")
    return _typed(rng, stem, ans, [total_runs, after_copy_all, max(0, ans - 1), ans + 1], why=why,
                  code="\n".join(lines), language="dockerfile",
                  check=_cache_check(steps, changed, ignored),
                  params={"kind": "cache", "steps": [[t, sorted(s) if s else None] for t, s in steps],
                          "changed": sorted(changed), "ignored": sorted(ignored)}, spread=2)


def _cache_check(steps, changed, ignored) -> str:
    rows = [(t, sorted(s) if s else None) for t, s in steps]
    return (f"steps = {rows!r}\nchanged = {sorted(changed)!r}\nignored = {sorted(ignored)!r}\n"
            "first = next((i for i, (t, s) in enumerate(steps) if s and any(\n"
            "    (c not in ignored) if '*' in s else (c in s) for c in changed)), None)\n"
            "print(0 if first is None else sum(t.startswith('RUN') for t, _ in steps[first:]))")


def _docker_multistage(rng: random.Random) -> Item:
    build_base = rng.choice([("golang:1.23", 820), ("node:20", 1100), ("rust:1.82", 1450), ("maven:3.9", 650)])
    final_base = rng.choice([("alpine:3.20", 8), ("debian:12-slim", 75), ("distroless/static", 2), ("scratch", 0)])
    deps, build = rng.randint(80, 400), rng.randint(20, 300)
    artifact = rng.randint(5, 60)
    extra = rng.choice([0, 0, rng.randint(3, 25)]) if final_base[1] >= 8 else 0
    lines = [f"FROM {build_base[0]} AS build        # {build_base[1]} МБ", "WORKDIR /src", "COPY . .",
             f"RUN make deps                    # +{deps} МБ", f"RUN make release                 # +{build} МБ, "
             f"бинарник {artifact} МБ", "", f"FROM {final_base[0]}" + (f"             # {final_base[1]} МБ"
                                                                     if final_base[1] else "             # пустой")]
    if extra:
        installer = "apk add --no-cache" if final_base[0].startswith("alpine") else "apt-get install -y"
        lines.append(f"RUN {installer} ca-certificates  # +{extra} МБ")
    lines += ["COPY --from=build /src/bin/app /app", 'ENTRYPOINT ["/app"]']
    ans = final_base[1] + extra + artifact
    everything = build_base[1] + deps + build + ans
    return _typed(rng, "Размер образа считайте суммой его слоёв. Сколько МБ весит итоговый образ?", ans,
                  [everything, build_base[1] + artifact, final_base[1] + extra + build, ans + deps],
                  code="\n".join(lines), language="dockerfile",
                  why="В итоговый образ попадает только последняя стадия: её база, её слои и то, что скопировано "
                      "через COPY --from. Стадия сборки остаётся в кэше и не публикуется.",
                  check=f"print({final_base[1]} + {extra} + {artifact})",
                  params={"kind": "multistage", "final": final_base[1], "extra": extra, "artifact": artifact},
                  spread=6)


def _docker_layers(rng: random.Random) -> Item:
    base = rng.choice([("ubuntu:24.04", 78), ("debian:12", 117), ("python:3.12-slim", 130)])
    archive, unpacked = rng.randint(100, 600), rng.randint(150, 900)
    together = rng.random() < 0.5
    url = "https://example.org/sdk.tar.gz"
    if together:
        body = [f"RUN curl -fsSL {url} -o /tmp/sdk.tgz \\", "    && tar -xzf /tmp/sdk.tgz -C /opt \\",
                "    && rm /tmp/sdk.tgz"]
        ans = base[1] + unpacked
        wrong = base[1] + archive + unpacked
    else:
        body = [f"RUN curl -fsSL {url} -o /tmp/sdk.tgz", "RUN tar -xzf /tmp/sdk.tgz -C /opt", "RUN rm /tmp/sdk.tgz"]
        ans = base[1] + archive + unpacked
        wrong = base[1] + unpacked
    lines = [f"FROM {base[0]}"] + body + ['CMD ["/opt/sdk/bin/run"]']
    return _typed(rng, f"База {base[0]} — {base[1]} МБ, архив sdk.tgz — {archive} МБ, распакованный SDK — "
                       f"{unpacked} МБ. Размер образа — сумма слоёв. Сколько МБ весит образ?", ans,
                  [wrong, base[1] + archive, archive + unpacked, unpacked],
                  code="\n".join(lines), language="dockerfile",
                  why="Каждая RUN — отдельный слой. Удаление в следующем слое только прячет файл, а байты остаются "
                      "в слое, где файл создан. Скачать, распаковать и удалить нужно в одной RUN.",
                  check=f"print({base[1]} + {unpacked}{'' if together else f' + {archive}'})",
                  params={"kind": "layers", "base": base[1], "archive": archive, "unpacked": unpacked,
                          "together": together}, spread=8)


def docker_generate(rng: random.Random, level: int, spec: str) -> Item:
    del spec
    if level == 1:
        return _docker_port(rng)
    if level == 2:
        return _docker_cache(rng, with_ignore=False)
    if level == 3:
        return _docker_multistage(rng)
    if level == 4:
        return _docker_layers(rng)
    return _docker_cache(rng, with_ignore=True)


# ---------------------------------------------------------------- Kubernetes

def _k8s_requests(rng: random.Random) -> Item:
    replicas = rng.randint(2, 9)
    cpu = rng.choice([100, 150, 200, 250, 300, 400, 500, 750])
    sidecar = rng.choice([0, 0, 50, 100])
    containers = [f"      - name: app\n        resources:\n          requests:\n            cpu: {cpu}m"]
    if sidecar:
        containers.append(f"      - name: proxy\n        resources:\n          requests:\n            cpu: {sidecar}m")
    code = (f"apiVersion: apps/v1\nkind: Deployment\nspec:\n  replicas: {replicas}\n  template:\n    spec:\n"
            "      containers:\n" + "\n".join(containers))
    ans = replicas * (cpu + sidecar)
    return _typed(rng, "Сколько миллиядер CPU (m) запросит у кластера весь Deployment?", ans,
                  [cpu + sidecar, replicas * cpu, ans + cpu], code=code, language="yaml",
                  why="Запрос пода — сумма запросов его контейнеров; Deployment запрашивает это на каждую реплику.",
                  check=f"print({replicas} * ({cpu} + {sidecar}))",
                  params={"kind": "requests", "replicas": replicas, "cpu": cpu, "sidecar": sidecar}, spread=50)


def surge_bounds(replicas: int, surge: str, unavailable: str) -> tuple[int, int]:
    """(max pods at once, min ready pods) for a RollingUpdate. A percentage surge rounds up, unavailable down."""
    def resolve(value: str, up: bool) -> int:
        if value.endswith("%"):
            exact = replicas * int(value[:-1]) / 100
            return math.ceil(exact) if up else math.floor(exact)
        return int(value)
    s, u = resolve(surge, True), resolve(unavailable, False)
    return replicas + s, replicas - u


def _k8s_rolling(rng: random.Random, percent: bool) -> Item:
    replicas = rng.randint(4, 15) if percent else rng.randint(3, 12)
    if percent:
        surge = f"{rng.choice([10, 20, 25, 30, 40, 50])}%"
        unavailable = f"{rng.choice([0, 10, 20, 25, 30])}%"
    else:
        surge, unavailable = str(rng.randint(1, 3)), str(rng.randint(0, 2))
    top, floor_ready = surge_bounds(replicas, surge, unavailable)
    ask_top = rng.random() < 0.5
    code = (f"spec:\n  replicas: {replicas}\n  strategy:\n    type: RollingUpdate\n    rollingUpdate:\n"
            f"      maxSurge: {surge}\n      maxUnavailable: {unavailable}")
    if ask_top:
        stem = ("Идёт выкатка новой версии. Какое наибольшее число подов (старых и новых) может существовать "
                "одновременно?")
        ans = top
    else:
        stem = "Идёт выкатка новой версии. Сколько подов как минимум остаётся готовыми к трафику в любой момент?"
        ans = floor_ready
    wrong = [replicas, top if not ask_top else floor_ready]
    if percent:
        exact_s = replicas * int(surge[:-1]) / 100
        exact_u = replicas * int(unavailable[:-1]) / 100
        wrong += [replicas + math.floor(exact_s), replicas - math.ceil(exact_u)]
    why = ("maxSurge — сколько подов сверх replicas можно создать, maxUnavailable — сколько можно недосчитаться. "
           "Проценты от replicas: maxSurge округляется вверх, maxUnavailable — вниз.")
    return _typed(rng, stem, ans, wrong, why=why, code=code, language="yaml",
                  check=(f"import math\nr = {replicas}\ns, u = '{surge}', '{unavailable}'\n"
                         "f = lambda v, up: (math.ceil if up else math.floor)(r * int(v[:-1]) / 100) "
                         "if v.endswith('%') else int(v)\n"
                         f"print({'r + f(s, True)' if ask_top else 'r - f(u, False)'})"),
                  params={"kind": "rolling", "replicas": replicas, "surge": surge, "unavailable": unavailable,
                          "ask_top": ask_top}, spread=2)


def hpa_desired(current: int, metric: int, target: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, math.ceil(current * metric / target)))


def _k8s_hpa(rng: random.Random) -> Item:
    while True:
        current = rng.randint(2, 12)
        target = rng.choice([50, 60, 70, 75, 80])
        metric = rng.randint(15, 160)
        if abs(metric / target - 1) > 0.15:      # outside the controller's 10 % tolerance band
            break
    lo = rng.randint(1, 3)
    hi = rng.randint(max(lo + 2, current), 20)
    ans = hpa_desired(current, metric, target, lo, hi)
    raw = math.ceil(current * metric / target)
    code = (f"apiVersion: autoscaling/v2\nkind: HorizontalPodAutoscaler\nspec:\n  minReplicas: {lo}\n"
            f"  maxReplicas: {hi}\n  metrics:\n  - type: Resource\n    resource:\n      name: cpu\n"
            f"      target:\n        type: Utilization\n        averageUtilization: {target}")
    return _typed(rng, f"Сейчас {current} реплик, средняя загрузка CPU {metric} % от запроса. "
                       "Сколько реплик выставит HPA на следующем шаге?", ans,
                  [raw, current * metric // target, current, round(current * target / metric)], code=code,
                  language="yaml",
                  why="desired = ceil(current × текущая метрика / целевая), затем ограничение minReplicas и "
                      "maxReplicas.",
                  check=f"import math\nprint(max({lo}, min({hi}, math.ceil({current} * {metric} / {target}))))",
                  params={"kind": "hpa", "current": current, "metric": metric, "target": target, "lo": lo,
                          "hi": hi}, spread=3)


def pending_pods(replicas: int, cpu: int, mem: int, nodes: list[tuple[int, int]]) -> int:
    fits = sum(min(free_cpu // cpu, free_mem // mem) for free_cpu, free_mem in nodes)
    return max(0, replicas - fits)


def _k8s_schedule(rng: random.Random) -> Item:
    cpu = rng.choice([250, 300, 500, 700, 1000])
    mem = rng.choice([256, 512, 768, 1024])
    nodes = [(rng.randint(1, 8) * 250, rng.randint(1, 8) * 512) for _ in range(rng.randint(2, 4))]
    fits_cpu = sum(c // cpu for c, _ in nodes)
    fits = sum(min(c // cpu, m // mem) for c, m in nodes)
    replicas = fits + rng.randint(1, 5) if rng.random() < 0.85 else max(1, fits - rng.randint(0, 1))
    ans = pending_pods(replicas, cpu, mem, nodes)
    table = "\n".join(f"node-{i + 1}: свободно cpu {c}m, memory {m}Mi" for i, (c, m) in enumerate(nodes))
    total = max(0, replicas - (sum(c for c, _ in nodes) // cpu))
    return _typed(rng, f"Под запрашивает cpu {cpu}m и memory {mem}Mi. Deployment просит {replicas} реплик. "
                       "Свободные ресурсы узлов ниже. Сколько подов останется в Pending?", ans,
                  [max(0, replicas - fits_cpu), total, ans + 1, replicas], code=table, language="text",
                  why="Планировщик ставит под на узел, только если там хватает каждого запрошенного ресурса. "
                      "Ресурсы разных узлов не складываются: на каждом узле помещается min(cpu, memory) подов.",
                  check=(f"nodes = {nodes!r}\nfit = sum(min(c // {cpu}, m // {mem}) for c, m in nodes)\n"
                         f"print(max(0, {replicas} - fit))"),
                  params={"kind": "schedule", "replicas": replicas, "cpu": cpu, "mem": mem,
                          "nodes": [list(n) for n in nodes]}, spread=2)


def k8s_generate(rng: random.Random, level: int, spec: str) -> Item:
    del spec
    if level == 1:
        return _k8s_requests(rng)
    if level == 2:
        return _k8s_rolling(rng, percent=False)
    if level == 3:
        return _k8s_rolling(rng, percent=True)
    if level == 4:
        return _k8s_hpa(rng)
    return _k8s_schedule(rng)


DOCKER = Family(
    id="docker_ops", title="Docker: образы, слои и кэш сборки", topic="infra", kind="code",
    specs=frozenset({"devops"}), skills=("Docker",), generate=docker_generate, a=1.3,
)
K8S = Family(
    id="k8s_ops", title="Kubernetes: запросы, выкатка и автомасштабирование", topic="infra", kind="code",
    specs=frozenset({"devops"}), skills=("Kubernetes",), generate=k8s_generate, a=1.3,
)
