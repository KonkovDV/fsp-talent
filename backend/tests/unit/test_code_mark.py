"""A shared shape is a review mark. A short answer and a different shape are not."""
from app.services.code_mark import compared, copy_mark, similar, source_language, template_grams, tokenize

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
    assert copy_mark("def solve(xs):\n    return xs[0] // 2  # half\n", []) is False
    assert len(tokenize("def solve(xs):\n    return xs // 2\n")) == len(tokenize("def solve(a):\n    return a // 9\n"))

    body = "".join(f"  let v{i} = {i} // step\n" for i in range(40))
    js = "function solve(xs) {\n" + body + "  return xs.length\n}\n"
    js_renamed = js.replace("xs", "items").replace("// step", "/* note */")
    assert source_language(js) == "javascript" and source_language(SHAPE) == "python"
    assert similar(js, js_renamed, "javascript") >= 0.85
    assert copy_mark(js, [js_renamed], "javascript") is True
    assert copy_mark(js, [SHAPE], "javascript") is False
    assert template_grams("javascript").isdisjoint(compared(js, "javascript"))
    js_other = "function solve(xs) {\n" + "".join(f"  if (xs[{i}]) return `{i}`\n" for i in range(40)) + "}\n"
    assert similar(js, js_other, "javascript") < 0.85
