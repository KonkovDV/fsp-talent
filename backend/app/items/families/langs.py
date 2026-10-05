"""The same counting programs written in several languages.

Loop counting has identical semantics in Python, JavaScript, Go and Java for the non-negative integers used
here (integer division of positive numbers, half-open ranges, naive recursion), so the answer is computed once
from the Python program and the candidate reads the language they chose before the test. Unit tests run
every language that is installed (node, go, java) and compare.
"""
from __future__ import annotations

LANGUAGES = ("python", "javascript", "go", "java")
LANGUAGE_LABELS = {"python": "Python", "javascript": "JavaScript", "go": "Go", "java": "Java"}


def _indent(text: str, prefix: str) -> str:
    return "\n".join(prefix + line if line else line for line in text.splitlines())


def loop_body(lang: str, kind: str, p: dict) -> str:
    """Body that increments `count`; kind: range | tri_lt | tri_ge | halve | pairs."""
    a, b, s, n, d, k = (p.get(x) for x in ("a", "b", "s", "n", "d", "k"))
    if lang == "python":
        return {
            "range": f"for i in range({a}, {b}, {s}):\n    count += 1",
            "tri_lt": f"for i in range({n}):\n    for j in range(i):\n        count += 1",
            "tri_ge": f"for i in range({n}):\n    for j in range(i, {n}):\n        count += 1",
            "halve": f"i = {n}\nwhile i > 1:\n    i //= {d}\n    count += 1",
            "pairs": f"for i in range({n}):\n    for j in range({n}):\n        if (i + j) % {k} == 0:\n            count += 1",
        }[kind]
    if lang == "javascript":
        return {
            "range": f"for (let i = {a}; i < {b}; i += {s}) {{\n  count++;\n}}",
            "tri_lt": f"for (let i = 0; i < {n}; i++) {{\n  for (let j = 0; j < i; j++) {{\n    count++;\n  }}\n}}",
            "tri_ge": f"for (let i = 0; i < {n}; i++) {{\n  for (let j = i; j < {n}; j++) {{\n    count++;\n  }}\n}}",
            "halve": f"let i = {n};\nwhile (i > 1) {{\n  i = Math.floor(i / {d});\n  count++;\n}}",
            "pairs": f"for (let i = 0; i < {n}; i++) {{\n  for (let j = 0; j < {n}; j++) {{\n"
                     f"    if ((i + j) % {k} === 0) count++;\n  }}\n}}",
        }[kind]
    if lang == "go":
        return {
            "range": f"for i := {a}; i < {b}; i += {s} {{\n\tcount++\n}}",
            "tri_lt": f"for i := 0; i < {n}; i++ {{\n\tfor j := 0; j < i; j++ {{\n\t\tcount++\n\t}}\n}}",
            "tri_ge": f"for i := 0; i < {n}; i++ {{\n\tfor j := i; j < {n}; j++ {{\n\t\tcount++\n\t}}\n}}",
            "halve": f"i := {n}\nfor i > 1 {{\n\ti /= {d}\n\tcount++\n}}",
            "pairs": f"for i := 0; i < {n}; i++ {{\n\tfor j := 0; j < {n}; j++ {{\n"
                     f"\t\tif (i+j)%{k} == 0 {{\n\t\t\tcount++\n\t\t}}\n\t}}\n}}",
        }[kind]
    return {   # java
        "range": f"for (int i = {a}; i < {b}; i += {s}) {{\n    count++;\n}}",
        "tri_lt": f"for (int i = 0; i < {n}; i++) {{\n    for (int j = 0; j < i; j++) {{\n        count++;\n    }}\n}}",
        "tri_ge": f"for (int i = 0; i < {n}; i++) {{\n    for (int j = i; j < {n}; j++) {{\n        count++;\n    }}\n}}",
        "halve": f"int i = {n};\nwhile (i > 1) {{\n    i /= {d};\n    count++;\n}}",
        "pairs": f"for (int i = 0; i < {n}; i++) {{\n    for (int j = 0; j < {n}; j++) {{\n"
                 f"        if ((i + j) % {k} == 0) count++;\n    }}\n}}",
    }[kind]


def loop_program(lang: str, kind: str, p: dict) -> str:
    body = loop_body(lang, kind, p)
    if lang == "python":
        return f"count = 0\n{body}\nprint(count)"
    if lang == "javascript":
        return f"let count = 0;\n{body}\nconsole.log(count);"
    if lang == "go":
        return f'package main\n\nimport "fmt"\n\nfunc main() {{\n\tcount := 0\n{_indent(body, chr(9))}\n\tfmt.Println(count)\n}}'
    return (f"public class Main {{\n    public static void main(String[] args) {{\n        int count = 0;\n"
            f"{_indent(body, ' ' * 8)}\n        System.out.println(count);\n    }}\n}}")


def fib_program(lang: str, n: int) -> str:
    if lang == "python":
        return ("count = 0\n\ndef f(n):\n    global count\n    count += 1\n    if n < 2:\n        return n\n"
                f"    return f(n - 1) + f(n - 2)\n\nf({n})\nprint(count)")
    if lang == "javascript":
        return ("let count = 0;\nfunction f(n) {\n  count++;\n  if (n < 2) return n;\n  return f(n - 1) + f(n - 2);\n}\n"
                f"f({n});\nconsole.log(count);")
    if lang == "go":
        return ('package main\n\nimport "fmt"\n\nvar count = 0\n\nfunc f(n int) int {\n\tcount++\n\tif n < 2 {\n\t\treturn n\n'
                f'\t}}\n\treturn f(n-1) + f(n-2)\n}}\n\nfunc main() {{\n\tf({n})\n\tfmt.Println(count)\n}}')
    return ("public class Main {\n    static int count = 0;\n\n    static int f(int n) {\n        count++;\n"
            "        if (n < 2) return n;\n        return f(n - 1) + f(n - 2);\n    }\n\n"
            f"    public static void main(String[] args) {{\n        f({n});\n        System.out.println(count);\n    }}\n}}")
