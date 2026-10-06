"""Data pipelines: full batches and late records. The answer is the integer the snippet prints."""
from __future__ import annotations

import random

from app.items import Family, Item, options_with


def _fill(rng: random.Random, value: int):
    def filler() -> int:
        shift = rng.choice([-4, -2, -1, 1, 2, 3, 6])
        return max(0, value + shift)
    return filler


def generate(rng: random.Random, level: int, spec: str) -> Item:
    del spec
    if level == 1:
        total = rng.randint(40, 400)
        size = rng.randint(5, 25)
        ans = total // size
        options, correct = options_with(rng, ans, [ans + 1, total % size, size], _fill(rng, ans))
        return Item(
            stem=f"В пачке {total} записей, размер пакета {size}. Сколько целых пакетов получится?",
            options=options, correct=correct,
            explanation="Целых пакетов — частное без остатка: записи // размер пакета.",
            verify={"runner": "python", "expect": str(ans),
                    "code": f"print({total} // {size})"},
        )
    if level == 2:
        rows = rng.randint(80, 500)
        nulls = rng.randint(1, rows // 4)
        ans = 100 * nulls // rows
        options, correct = options_with(rng, ans, [ans + 1, max(0, ans - 1), nulls], _fill(rng, ans))
        return Item(
            stem=f"В таблице {rows} строк, пустых значений в столбце {nulls}. Сколько это целых процентов?",
            options=options, correct=correct,
            explanation="Целый процент пустых — 100 × пустые // все строки.",
            verify={"runner": "python", "expect": str(ans),
                    "code": f"print(100 * {nulls} // {rows})"},
        )
    if level == 3:
        keys = [rng.randint(0, 12) for _ in range(12)]
        ans = len(set(keys))
        options, correct = options_with(rng, ans, [len(keys), max(1, ans - 1), ans + 1], _fill(rng, ans))
        shown = ", ".join(str(k) for k in keys)
        return Item(
            stem=f"Ключи записей: {shown}. Сколько разных ключей останется после удаления повторов?",
            options=options, correct=correct,
            explanation="Повтор ключа не создаёт новую запись: считается размер множества.",
            verify={"runner": "python", "expect": str(ans),
                    "code": f"print(len(set({keys})))"},
        )
    if level == 4:
        parts = rng.randint(4, 16)
        key = rng.randint(0, 10_000)
        ans = key % parts
        options, correct = options_with(rng, ans, [(key + 1) % parts, parts, key % (parts + 1)], _fill(rng, ans))
        return Item(
            stem=f"Ключ {key} раскладывается по {parts} разделам остатком от деления. Какой номер раздела?",
            options=options, correct=correct,
            explanation="Номер раздела — остаток ключа по числу разделов.",
            verify={"runner": "python", "expect": str(ans),
                    "code": f"print({key} % {parts})"},
        )
    arrived = rng.randint(30, 240)
    size = rng.randint(8, 20)
    ans = arrived % size
    options, correct = options_with(rng, ans, [arrived // size, size, ans + 1], _fill(rng, ans))
    return Item(
        stem=f"Пришло {arrived} записей, пакет вмещает {size}. Сколько записей останется в неполном пакете?",
        options=options, correct=correct,
        explanation="Хвост — остаток от деления числа записей на размер пакета.",
        verify={"runner": "python", "expect": str(ans),
                "code": f"print({arrived} % {size})"},
    )


FAMILY = Family(
    id="data_batches", title="Конвейер: пакеты и повторы", topic="pipelines", kind="code",
    specs=frozenset({"data"}), skills=("Airflow",), generate=generate, a=1.3,
)


def generate_late(rng: random.Random, level: int, spec: str) -> Item:
    """A second pipeline family so a full session does not run out of items."""
    del spec, level
    event = rng.randint(0, 80)
    delay = rng.randint(5, 90)
    allowed = rng.randint(0, 20)
    ans = max(0, delay - allowed)
    options, correct = options_with(rng, ans, [delay, allowed, delay + allowed], _fill(rng, ans))
    return Item(
        stem=(f"Событие отмечено на минуте {event}, запись пришла через {delay} минут. "
              f"Допустимое опоздание {allowed} минут. На сколько минут запись опоздала сверх допуска?"),
        options=options, correct=correct,
        explanation="Сверх допуска остаётся только положительная разность задержки и допуска.",
        verify={"runner": "python", "expect": str(ans),
                "code": f"print(max(0, {delay} - {allowed}))"},
    )


FAMILY_LATE = Family(
    id="data_late", title="Конвейер: опоздавшие записи", topic="pipelines", kind="code",
    specs=frozenset({"data"}), skills=("Spark",), generate=generate_late, a=1.2,
)
