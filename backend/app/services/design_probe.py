"""A parametric layout check. Contrast and geometry are computed. Taste is not a score.

The grade does not move.
"""
from __future__ import annotations

import hashlib

CHOICES = ("контраст ниже 4,5", "фигуры пересекаются", "текст вне листа", "дефекта нет")
_FLOOR = 4.5


def _channel(value: float) -> float:
    unit = value / 255
    if unit <= 0.04045:
        return unit / 12.92
    return ((unit + 0.055) / 1.055) ** 2.4


def luminance(rgb: tuple[int, int, int]) -> float:
    red, green, blue = rgb
    return 0.2126 * _channel(red) + 0.7152 * _channel(green) + 0.0722 * _channel(blue)


def contrast_ratio(fg: tuple[int, int, int], bg: tuple[int, int, int]) -> float:
    lighter = max(luminance(fg), luminance(bg))
    darker = min(luminance(fg), luminance(bg))
    return (lighter + 0.05) / (darker + 0.05)


def _overlaps(a: tuple[int, int, int, int], b: tuple[int, int, int, int]) -> bool:
    ax, ay, aw, ah = a
    bx, by, bw, bh = b
    return ax < bx + bw and bx < ax + aw and ay < by + bh and by < ay + ah


def _inside(box: tuple[int, int, int, int], sheet: tuple[int, int]) -> bool:
    x, y, w, h = box
    width, height = sheet
    return x >= 0 and y >= 0 and x + w <= width and y + h <= height


def _case(kind: str) -> dict:
    sheet = (360, 640)
    if kind == "contrast":
        fg, bg = (170, 170, 170), (255, 255, 255)
        lines = [
            "Лист 360×640.",
            f"Текст RGB{fg} на фоне RGB{bg}.",
            "Один блок 40,40 размером 80×32, внутри листа.",
        ]
        answer = "контраст ниже 4,5" if contrast_ratio(fg, bg) < _FLOOR else "дефекта нет"
    elif kind == "overlap":
        first, second = (40, 40, 100, 80), (90, 70, 100, 80)
        lines = [
            "Лист 360×640.",
            "Текст RGB(0, 0, 0) на фоне RGB(255, 255, 255).",
            f"Блок {first[0]},{first[1]} размером {first[2]}×{first[3]}.",
            f"Блок {second[0]},{second[1]} размером {second[2]}×{second[3]}.",
        ]
        answer = "фигуры пересекаются" if _overlaps(first, second) else "дефекта нет"
    else:
        box = (300, 20, 80, 24)
        lines = [
            "Лист 360×640.",
            "Текст RGB(0, 0, 0) на фоне RGB(255, 255, 255).",
            f"Подпись {box[0]},{box[1]} размером {box[2]}×{box[3]}.",
        ]
        answer = "текст вне листа" if not _inside(box, sheet) else "дефекта нет"
    return {"lines": lines, "answer": answer}


def puzzle(seed: str) -> dict:
    kind = ("contrast", "overlap", "outside")[int(hashlib.sha256(seed.encode()).hexdigest(), 16) % 3]
    case = _case(kind)
    return {"seed": seed, "lines": case["lines"], "choices": list(CHOICES), "grade_unchanged": True}


def judge(seed: str, choice: str) -> dict:
    case = _case(("contrast", "overlap", "outside")[int(hashlib.sha256(seed.encode()).hexdigest(), 16) % 3])
    return {"matched": choice == case["answer"], "grade_unchanged": True}
