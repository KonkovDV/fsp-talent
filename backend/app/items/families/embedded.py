"""Embedded: number representation, bit masks, overflow and byte order."""
from __future__ import annotations

import random
import struct

from app.items import Family, Item, near_int, options_with


def _int8(v: int) -> int:
    return ((v + 128) % 256) - 128


def generate(rng: random.Random, level: int, spec: str) -> Item:
    if level == 1:
        v = rng.randint(40, 4000)
        hex_digits = f"{v:X}"
        misread = int(hex_digits) if hex_digits.isdigit() else v - 16   # hex read as decimal
        options, correct = options_with(rng, v, [misread, v + 16, v * 2], near_int(rng, v, 30))
        return Item(stem=f"Чему равно 0x{v:X} в десятичной системе?", options=options, correct=correct,
                    explanation="Каждая шестнадцатеричная цифра — 4 бита, разряды — степени 16.",
                    verify={"runner": "python", "code": f"print(0x{v:X})", "expect": str(v)})
    if level == 2:
        x = rng.randint(0, 255)
        s, c = rng.sample(range(8), 2)
        code = f"x = 0b{x:08b}\nx |= 1 << {s}\nx &= ~(1 << {c})\nprint(x)"
        ans = (x | (1 << s)) & ~(1 << c)
        wrong = [x | (1 << s), x & ~(1 << c), (x | s) & ~c]
        options, correct = options_with(rng, ans, wrong, near_int(rng, ans, 8))
        return Item(stem="Что выведет код (Python, те же правила, что в C)?", code=code, language="python",
                    options=options, correct=correct, explanation="|= 1 << n ставит бит n, &= ~(1 << n) сбрасывает.",
                    verify={"runner": "python", "code": code, "expect": str(ans)})
    if level == 3:
        a, b = rng.randint(60, 127), rng.randint(30, 120)
        ans = _int8(a + b)
        code = f"int8_t a = {a};\na += {b};\nprintf(\"%d\", a);"
        options, correct = options_with(rng, ans, [a + b, (a + b) % 128, -(a + b) % 128], near_int(rng, ans, 6))
        return Item(stem="Что напечатает код на типичной платформе (дополнительный код, 8 бит)?", code=code,
                    language="c", options=options, correct=correct,
                    explanation="int8_t хранит −128…127; при выходе за диапазон значение заворачивается по модулю 256.",
                    verify={"runner": "python", "code": f"print((({a} + {b} + 128) % 256) - 128)", "expect": str(ans)})
    if level == 4:
        v = rng.randint(0x10000000, 0xFFFFFFFF)
        off = rng.randint(0, 3)
        little = struct.pack("<I", v)
        ans = f"0x{little[off]:02X}"
        big = struct.pack(">I", v)
        wrong = [f"0x{big[off]:02X}", f"0x{little[3 - off]:02X}", f"0x{(v >> (8 * off + 4)) & 0xFF:02X}"]
        options, correct = options_with(rng, ans, [w for w in wrong if w != ans],
                                        lambda: f"0x{rng.randint(0, 255):02X}")
        return Item(stem=f"uint32_t x = 0x{v:08X} лежит в памяти little-endian. Какой байт по адресу &x + {off}?",
                    options=options, correct=correct,
                    explanation="Little-endian кладёт младший байт по младшему адресу.",
                    verify={"runner": "python",
                            "code": f"import struct\nprint(f'0x{{struct.pack(\"<I\", {v})[{off}]:02X}}')",
                            "expect": ans})
    a, b = rng.randint(300, 4000), rng.randint(20, 200)
    ans = (a * b) % 65536
    code = f"uint16_t x = {a};\nx = x * {b};\nprintf(\"%u\", x);"
    options, correct = options_with(rng, ans, [a * b, (a * b) % 32768, (a * b) // 65536], near_int(rng, ans, 50))
    return Item(stem="Что напечатает код?", code=code, language="c", options=options, correct=correct,
                explanation="Произведение вычисляется в int, а при записи в uint16_t берётся по модулю 65536.",
                verify={"runner": "python", "code": f"print(({a} * {b}) % 65536)", "expect": str(ans)})


FAMILY = Family(
    id="emb_bits", title="Встраиваемые системы: биты и представление чисел", topic="embedded", kind="code",
    specs=frozenset({"embedded", "mobile", "security"}), skills=("C",), generate=generate, a=1.4,
)
