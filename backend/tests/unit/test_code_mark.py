"""A shared shape is a review mark. A short answer and a different shape are not."""
from app.services.code_mark import compared, copy_mark, similar, template_grams

SHAPE = "def solve(xs):\n" + "".join(f"    x{i} = {i}\n" for i in range(40)) + "    return sum(xs)\n"


def test_a_renamed_copy_is_marked_and_a_short_answer_is_not():
    renamed = SHAPE.replace("xs", "items")
    assert similar(SHAPE, renamed) >= 0.85
    assert copy_mark(SHAPE, [renamed]) is True
    assert similar("def solve(x):\n    return x\n", SHAPE) == 0
    assert copy_mark("def solve(x):\n    return 1\n", [SHAPE]) is False
    header = template_grams()
    assert header
    assert header.isdisjoint(compared(SHAPE))
    other = "def solve(xs):\n" + "".join(f"    return xs[{i}]\n" for i in range(40))
    assert similar(SHAPE, other) < 0.85
