"""Load check for TZ 3.5: «стабильная работа при одновременном использовании десятками пользователей».

Registers the users it needs (codes are read like in the smoke test), then runs virtual users at once for a
fixed time. Each user repeats a realistic loop with a pause between requests: employers search the bank,
open shortlists and their vacancies; candidates open their profile, vacancies, the task of the week and
notifications. Prints a Markdown table: requests, errors, p50/p95/p99 per operation.

    python tests/load_api.py --users 40 --seconds 60      # against SMOKE_BASE, demo data loaded
    python tests/load_api.py --scenario shortlist --seconds 60 --reuse
"""
from __future__ import annotations

import argparse
import asyncio
import os
import random
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

import httpx

sys.path.insert(0, str(Path(__file__).parent))
from smoke_api import BASE, last_letter  # noqa: E402

PASSWORD = "load-pass-1"
QUERIES = ["Python backend", "Go PostgreSQL", "React TypeScript", "pentest Linux", "PyTorch NLP", "C++ STM32"]


async def _register(client: httpx.AsyncClient, role: str, tag: str) -> str:
    email = f"load-{role}-{tag}-{int(time.time() * 1000)}@example.com"
    if role == "participant":
        body = {"email": email, "password": PASSWORD, "display_name": "Нагрузка", "is_adult": True,
                "consents": ["terms", "pd_candidate"]}
    else:
        body = {"email": email, "password": PASSWORD, "company_name": f"Нагрузка {tag}",
                "consents": ["terms", "pd_employer"]}
    while True:
        r = await client.post(f"/auth/{role}/register", json=body)
        if r.status_code != 429:   # the site allows 30 registrations a minute: wait for the next window
            break
        await asyncio.sleep(int(r.headers.get("Retry-After", "60")) + 1)
    assert r.status_code == 202, r.text
    code = await asyncio.to_thread(last_letter, email)
    r = await client.post("/auth/verify-email", json={"email": email, "code": code["code"], "role": role})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


async def _login(client: httpx.AsyncClient, role: str, email: str, password: str = "demo12345") -> str:
    r = await client.post(f"/auth/{role}/token", data={"username": email, "password": password})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


async def _token(client: httpx.AsyncClient, role: str, email: str, tag: str, reuse: bool) -> str:
    """Stable load accounts log in again. A fresh run registers, waiting out the site limit of 30 a minute."""
    if reuse:
        r = await client.post(f"/auth/{role}/token", data={"username": email, "password": PASSWORD})
        if r.status_code == 200:
            return r.json()["access_token"]
    return await _register(client, role, tag) if not reuse else await _register_fixed(client, role, email, tag)


async def _register_fixed(client: httpx.AsyncClient, role: str, email: str, tag: str) -> str:
    if role == "participant":
        body = {"email": email, "password": PASSWORD, "display_name": "Нагрузка", "is_adult": True,
                "consents": ["terms", "pd_candidate"]}
    else:
        body = {"email": email, "password": PASSWORD, "company_name": f"Нагрузка {tag}",
                "consents": ["terms", "pd_employer"]}
    while True:
        r = await client.post(f"/auth/{role}/register", json=body)
        if r.status_code != 429:
            break
        await asyncio.sleep(int(r.headers.get("Retry-After", "60")) + 1)
    assert r.status_code == 202, r.text
    code = await asyncio.to_thread(last_letter, email)
    r = await client.post("/auth/verify-email", json={"email": email, "code": code["code"], "role": role})
    assert r.status_code == 200, r.text
    return r.json()["access_token"]


async def _user(client, token, ops, stats, until, rng):
    headers = {"Authorization": f"Bearer {token}"}
    while time.perf_counter() < until:
        name, path = rng.choice(ops)
        start = time.perf_counter()
        try:
            r = await client.get(path() if callable(path) else path, headers=headers)
            code = r.status_code
        except httpx.HTTPError:
            code = 0
        stats[name].append((time.perf_counter() - start, code))
        await asyncio.sleep(rng.uniform(0.5, 1.5))   # a person reads the page before the next click


def _employer_ops(rng, need_id=None):
    ops = [("Поиск по банку кандидатов", lambda: "/search/candidates?q=" + rng.choice(QUERIES) + "&limit=20"),
           ("Вакансии компании", "/vacancies/mine"), ("Профиль компании", "/employer/me")]
    if need_id:
        ops.append(("Подборка по потребности", f"/needs/{need_id}/matches"))
    return ops


CANDIDATE_OPS = [("Профиль кандидата", "/candidates/me"), ("Вакансии под профиль", "/vacancies/for-me"),
                 ("Задача недели", "/assessment/practice/weekly"), ("Уведомления", "/notifications")]


SHORTLIST_NEEDS = (
    ("Нагрузка: backend", {"role": "backend", "grade": "middle", "skills": ["Python", "PostgreSQL"]}),
    ("Нагрузка: frontend", {"role": "frontend", "grade": "junior", "skills": ["TypeScript", "React"]}),
    ("Нагрузка: ml", {"role": "ml", "grade": "middle", "skills": ["Python", "PyTorch"]}),
)


def _print(stats: dict, seconds: int, employers: int, candidates: int, elapsed: float, note: str) -> None:
    total = sum(len(v) for v in stats.values())
    if note:
        print(note)
    print(f"Пользователей одновременно: {employers + candidates} "
          f"({employers} работодателей, {candidates} кандидатов), {seconds} с, "
          f"запросов: {total}, {total / elapsed:.1f} в секунду.\n")
    print("| Операция | Запросов | Ошибок 5xx и сетевых | Ответов 429 | p50, мс | p95, мс | p99, мс |")
    print("|---|---|---|---|---|---|---|")
    for name, rows in sorted(stats.items()):
        times = sorted(t * 1000 for t, _ in rows)
        q = statistics.quantiles(times, n=100) if len(times) > 1 else times * 99
        errors = sum(1 for _, c in rows if c == 0 or c >= 500)
        limited = sum(1 for _, c in rows if c == 429)
        print(f"| {name} | {len(rows)} | {errors} | {limited} | {q[49]:.0f} | {q[94]:.0f} | {q[98]:.0f} |")


async def _ensure_needs(client, token) -> list[str]:
    headers = {"Authorization": f"Bearer {token}"}
    existing = (await client.get("/needs", headers=headers)).json()
    by_title = {row["title"]: row["id"] for row in existing}
    ids = []
    for title, params in SHORTLIST_NEEDS:
        if title in by_title:
            ids.append(by_title[title])
            continue
        r = await client.post("/needs", headers=headers, json={"title": title, "params": params})
        assert r.status_code == 201, r.text
        ids.append(r.json()["id"])
    return ids


async def _shortlist_user(client, token, need_ids, stats, until, rng):
    headers = {"Authorization": f"Bearer {token}"}
    pages = (0, 20, 40)
    while time.perf_counter() < until:
        need_id = rng.choice(need_ids)
        offset = rng.choice(pages)
        start = time.perf_counter()
        try:
            r = await client.get(f"/needs/{need_id}/matches?limit=20&offset={offset}", headers=headers)
            code = r.status_code
        except httpx.HTTPError:
            code = 0
        stats["Подборка по потребности"].append((time.perf_counter() - start, code))
        await asyncio.sleep(rng.uniform(3.0, 3.6))   # under the 30 searches a minute limit


async def main(users: int, seconds: int, scenario: str, reuse: bool, note: str) -> None:
    limits = httpx.Limits(max_connections=max(users, 40) * 2, max_keepalive_connections=max(users, 40) * 2)
    async with httpx.AsyncClient(base_url=BASE, timeout=60, limits=limits) as client:
        if scenario == "shortlist":
            tokens_e = []
            for i in range(20):
                email = f"load-e-{i:02d}@example.com"
                tokens_e.append(await _token(client, "employer", email, str(i), reuse))
            need_ids = [await _ensure_needs(client, token) for token in tokens_e]
            stats: dict[str, list] = defaultdict(list)
            until = time.perf_counter() + seconds
            started = time.perf_counter()
            await asyncio.gather(*[
                _shortlist_user(client, token, ids, stats, until, random.Random(i))
                for i, (token, ids) in enumerate(zip(tokens_e, need_ids, strict=True))
            ])
            _print(stats, seconds, len(tokens_e), 0, time.perf_counter() - started, note)
            return

        employers = users // 2
        candidates = users - employers
        tokens_e = [await _login(client, "employer", "hr@sibcode.demo")]
        for i in range(employers - 1):
            email = f"load-e-{i:02d}@example.com"
            if reuse:
                tokens_e.append(await _token(client, "employer", email, str(i), True))
            else:
                tokens_e.append(await _register(client, "employer", str(i)))
        tokens_c = [await _login(client, "participant", e) for e in ("fsp001@demo.talent", "fsp002@demo.talent",
                                                                     "nofsp@demo.talent")]
        for i in range(max(0, candidates - 3)):
            email = f"load-c-{i:02d}@example.com"
            if reuse:
                tokens_c.append(await _token(client, "participant", email, str(i), True))
            else:
                tokens_c.append(await _register(client, "participant", str(i)))
        needs = (await client.get("/needs", headers={"Authorization": f"Bearer {tokens_e[0]}"})).json()
        need_id = needs[0]["id"] if needs else None

        stats = defaultdict(list)
        until = time.perf_counter() + seconds
        tasks = []
        for i, token in enumerate(tokens_e):
            rng = random.Random(i)
            tasks.append(_user(client, token, _employer_ops(rng, need_id if i == 0 else None), stats, until, rng))
        for i, token in enumerate(tokens_c):
            tasks.append(_user(client, token, CANDIDATE_OPS, stats, until, random.Random(1000 + i)))
        started = time.perf_counter()
        await asyncio.gather(*tasks)
        _print(stats, seconds, len(tokens_e), len(tokens_c), time.perf_counter() - started, note)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--users", type=int, default=int(os.environ.get("LOAD_USERS", 40)))
    parser.add_argument("--seconds", type=int, default=60)
    parser.add_argument("--scenario", choices=("mixed", "shortlist"), default="mixed")
    parser.add_argument("--reuse", action="store_true")
    parser.add_argument("--note", default="")
    args = parser.parse_args()
    asyncio.run(main(args.users, args.seconds, args.scenario, args.reuse, args.note))
