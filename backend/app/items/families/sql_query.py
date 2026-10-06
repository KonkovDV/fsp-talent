"""SQL: result of a query over a tiny table. The answer comes from running the query in SQLite."""
from __future__ import annotations

import random
import sqlite3

from app.items import Family, Item, near_int, options_with

DEPTS = ["dev", "ops", "qa", "data", "sales", "hr"]


def run_sql(schema: str, query: str):
    con = sqlite3.connect(":memory:")
    try:
        con.executescript(schema)
        row = con.execute(query).fetchone()
        return row[0] if row else None
    finally:
        con.close()


def _table(rng: random.Random, with_null_manager: bool = False):
    n = rng.randint(6, 9)
    depts = rng.sample(DEPTS, k=rng.randint(3, 4))
    salaries = rng.sample(range(80, 300, 5), k=n)
    rows = []
    for i in range(1, n + 1):
        manager = None if i == 1 else rng.randint(1, max(1, i - 1))
        bonus = None if rng.random() < 0.35 else rng.choice([5, 10, 15, 20])
        rows.append((i, rng.choice(depts), salaries[i - 1], manager, bonus))
    if with_null_manager and all(r[3] is not None for r in rows):
        rows[0] = (*rows[0][:3], None, rows[0][4])
    all_depts = depts + rng.sample([d for d in DEPTS if d not in depts], k=rng.randint(1, 2))
    return rows, all_depts


def _schema(rows, depts) -> str:
    def sql(v):
        return "NULL" if v is None else (f"'{v}'" if isinstance(v, str) else str(v))
    lines = ["CREATE TABLE emp (id INT, dept TEXT, salary INT, manager_id INT, bonus INT);",
             "CREATE TABLE dept (name TEXT);"]
    lines += [f"INSERT INTO emp VALUES ({', '.join(sql(v) for v in r)});" for r in rows]
    lines += [f"INSERT INTO dept VALUES ('{d}');" for d in depts]
    return "\n".join(lines)


def _show(rows, depts) -> str:
    head = "emp(id, dept, salary, manager_id, bonus)\n"
    body = "\n".join(f"  {r[0]:>2} | {r[1]:<5} | {r[2]:>3} | {('NULL' if r[3] is None else r[3]):>4} | "
                     f"{'NULL' if r[4] is None else r[4]}" for r in rows)
    return f"{head}{body}\ndept(name): {', '.join(depts)}"


def generate(rng: random.Random, level: int, spec: str) -> Item:
    rows, depts = _table(rng, with_null_manager=level == 5)
    schema = _schema(rows, depts)
    salaries = sorted(r[2] for r in rows)
    if level == 1:
        t = rng.choice(salaries[1:-1])
        query = f"SELECT COUNT(*) FROM emp WHERE salary > {t};"
        wrong = [sum(s >= t for s in salaries), sum(s < t for s in salaries), len(rows)]
        why = f"> {t} не включает строку с зарплатой ровно {t}."
    elif level == 2:
        k = rng.choice([2, 3])
        query = f"SELECT COUNT(*) FROM (SELECT dept FROM emp GROUP BY dept HAVING COUNT(*) >= {k});"
        groups = {}
        for r in rows:
            groups[r[1]] = groups.get(r[1], 0) + 1
        wrong = [len(groups), sum(v > k for v in groups.values()), sum(v for v in groups.values() if v >= k)]
        why = "HAVING фильтрует группы после GROUP BY; считаем число отделов, а не сотрудников."
    elif level == 3:
        query = "SELECT COUNT(*) FROM dept d LEFT JOIN emp e ON e.dept = d.name WHERE e.id IS NULL;"
        used = {r[1] for r in rows}
        wrong = [len(depts), len(used), len(rows) - len(used)]
        why = "LEFT JOIN оставляет отделы без сотрудников с NULL в колонках emp — их и считает условие IS NULL."
    elif level == 4:
        query = ("SELECT MAX(salary) FROM (SELECT salary, ROW_NUMBER() OVER "
                 "(PARTITION BY dept ORDER BY salary DESC) AS rn FROM emp) WHERE rn = 2;")
        wrong = [salaries[-1], salaries[-2], salaries[-3] if len(salaries) > 2 else salaries[0]]
        why = "ROW_NUMBER нумерует внутри каждого отдела; rn = 2 — вторая зарплата отдела, из них берётся максимум."
    else:
        if rng.random() < 0.5:
            query = "SELECT COUNT(*) FROM emp WHERE id NOT IN (SELECT manager_id FROM emp);"
            managers = {r[3] for r in rows if r[3] is not None}
            wrong = [len([r for r in rows if r[0] not in managers]), len(rows) - 1, len(managers)]
            why = ("В подзапросе есть NULL: x NOT IN (…, NULL) никогда не бывает истинным, поэтому 0. "
                   "Безопасный вариант — NOT EXISTS.")
        else:
            query = "SELECT CAST(AVG(bonus) AS INT) + COUNT(bonus) FROM emp;"
            bonuses = [r[4] for r in rows]
            known = [b for b in bonuses if b is not None]
            if not known:
                rows[0] = (*rows[0][:4], 10)
                schema = _schema(rows, depts)
                known = [10]
            avg_all = int(sum(known) / len(rows))
            wrong = [avg_all + len(rows), avg_all + len(known), int(sum(known) / len(known)) + len(rows)]
            why = "AVG и COUNT(колонка) пропускают NULL; COUNT(*) считал бы все строки."
    answer = run_sql(schema, query)
    options, correct = options_with(rng, answer, wrong, near_int(rng, int(answer or 0), 4))
    return Item(stem=f"Таблицы:\n{_show(rows, depts)}\n\nЧто вернёт запрос?", code=query, language="sql",
                options=options, correct=correct, explanation=why,
                verify={"runner": "sqlite", "schema": schema, "query": query, "expect": str(answer)})


FAMILY = Family(
    id="sql_query", title="SQL: результат запроса", topic="sql", kind="code",
    specs=frozenset({"backend", "fullstack", "ml", "qa", "analyst", "data"}), skills=("SQL",), generate=generate, a=1.4,
)
