"""Narrow code families must not repeat often: 20 leaked sessions should not cover their instances."""
import random

import pytest

from app.items.families import algorithms, python_code


@pytest.mark.parametrize("gen,level,minimum", [
    (algorithms.ops_generate, 2, 400),
    (algorithms.ops_generate, 4, 200),
    (python_code.generate, 2, 400),
])
def test_level_has_many_instances(gen, level, minimum):
    rng = random.Random(5)
    seen = {(it.stem, it.code) for it in (gen(rng, level, "backend") for _ in range(3000))}
    assert len(seen) >= minimum


def test_wider_items_keep_correct_key():
    rng = random.Random(9)
    for _ in range(30):
        item = python_code.generate(rng, 2, "backend")
        assert python_code.run_python(item.code) == item.options[item.correct]
