"""Resume text from an uploaded PDF, and a profile PDF the candidate can download.

The file is not stored: only the extracted text is parsed into skills. The profile PDF is built
in memory. Cyrillic needs a TrueType font with Cyrillic glyphs: the backend image installs
`fonts-dejavu-core` (backend/Dockerfile); a local run finds DejaVu or Liberation on Linux and Arial on
Windows or macOS. Names are never transliterated: without such a font the PDF is refused loudly.
"""
from __future__ import annotations

import io
import math
from pathlib import Path

from pypdf import PdfReader

MAX_PDF_BYTES = 5_000_000
MAX_PDF_PAGES = 30
MIN_VISIBLE_PT = 2.0
LIGHT_INK = 0.85
_INVISIBLE = dict.fromkeys(map(ord, "\u200b\u200c\u200d\u2060\ufeff\u00ad"))
_FONTS = (
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
    Path(r"C:\Windows\Fonts\arial.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    Path("/Library/Fonts/Arial.ttf"),
)


def _scale(matrix) -> float:
    if not matrix or len(matrix) < 2:
        return 1.0
    return math.hypot(float(matrix[0]), float(matrix[1])) or 1.0


def rendered_size(font_size: float, tm, cm) -> float:
    return abs(float(font_size or 0)) * _scale(tm) * _scale(cm)


def text_origin(tm, cm) -> tuple[float, float]:
    e = float(tm[4]) if tm and len(tm) > 4 else 0.0
    f = float(tm[5]) if tm and len(tm) > 5 else 0.0
    if not cm or len(cm) < 6:
        return e, f
    return (
        float(cm[0]) * e + float(cm[2]) * f + float(cm[4]),
        float(cm[1]) * e + float(cm[3]) * f + float(cm[5]),
    )


def keep_span(*, gray: float, mode: int, size: float, x: float, y: float,
              box: tuple[float, float, float, float]) -> bool:
    """Visible ink on the page. White, tiny, invisible and off-page runs are dropped."""
    if mode == 3 or gray >= LIGHT_INK or size < MIN_VISIBLE_PT:
        return False
    x0, y0, x1, y1 = box
    slack = 4.0
    return (x0 - slack) <= x <= (x1 + slack) and (y0 - slack) <= y <= (y1 + slack)


def strip_invisible(text: str) -> str:
    return text.translate(_INVISIBLE)


class _Ink:
    def __init__(self, box: tuple[float, float, float, float]) -> None:
        self.box = box
        self.gray = 0.0
        self.mode = 0
        self.parts: list[str] = []

    def before(self, operator, operands, _cm, _tm) -> None:
        op = operator.decode() if isinstance(operator, bytes) else str(operator)
        try:
            if op in {"g", "G"} and operands:
                self.gray = float(operands[0])
            elif op in {"rg", "RG"} and len(operands) >= 3:
                self.gray = min(float(operands[0]), float(operands[1]), float(operands[2]))
            elif op in {"k", "K"} and len(operands) >= 4:
                cyan, magenta, yellow, black = (float(value) for value in operands[:4])
                self.gray = 1.0 - min(1.0, black + max(cyan, magenta, yellow))
            elif op in {"sc", "SC", "scn", "SCN"} and operands:
                nums = []
                for value in operands:
                    try:
                        nums.append(float(value))
                    except (TypeError, ValueError):
                        continue
                if len(nums) == 4:
                    cyan, magenta, yellow, black = nums
                    self.gray = 1.0 - min(1.0, black + max(cyan, magenta, yellow))
                elif nums:
                    self.gray = min(nums)
            elif op == "Tr" and operands:
                self.mode = int(operands[0])
        except (TypeError, ValueError):
            return

    def take(self, text, cm, tm, _font, font_size) -> None:
        if not text:
            return
        x, y = text_origin(tm, cm)
        if keep_span(gray=self.gray, mode=self.mode, size=rendered_size(font_size, tm, cm),
                     x=x, y=y, box=self.box):
            self.parts.append(text)


def _page_box(page) -> tuple[float, float, float, float]:
    box = page.mediabox
    return float(box[0]), float(box[1]), float(box[2]), float(box[3])


def _page_text(page) -> str:
    ink = _Ink(_page_box(page))
    page.extract_text(visitor_operand_before=ink.before, visitor_text=ink.take)
    return "".join(ink.parts)


def extract_pdf_text(data: bytes) -> str:
    if len(data) > MAX_PDF_BYTES or not data.startswith(b"%PDF"):
        raise ValueError("pdf")
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ValueError("pdf")
        pages = list(reader.pages)[:MAX_PDF_PAGES]
        text = "\n".join(_page_text(page) for page in pages)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("pdf") from exc
    return strip_invisible(text).strip()[:20000]


def _font() -> Path | None:
    return next((path for path in _FONTS if path.is_file()), None)


def profile_lines(name: str | None, role: str | None, grade: str | None,
                  skills: list[str], disciplines: list[dict]) -> list[str]:
    title = name or "Кандидат"
    lines = ["ФСП Талант", title, ""]
    if role or grade:
        lines.append(f"Категория: {role or '—'} {grade or ''}".strip())
    if skills:
        lines.append("Навыки: " + ", ".join(skills))
    for row in disciplines:
        rank = row.get("rank") or "—"
        assigned = row.get("rank_assigned_at")
        order = row.get("rank_order_ref")
        extra = f", присвоен {assigned}, {order}" if assigned or order else ""
        lines.append(f"{row['label']}: нижняя граница {row['lcb']:.2f}, присвоенный разряд {rank}{extra}")
    lines.append("")
    lines.append("Контакты в этот файл не входят.")
    return lines


def render_profile_pdf(lines: list[str]) -> bytes:
    from fpdf import FPDF

    pdf = FPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=15)
    font = _font()
    if font is None:
        # Helvetica has no Cyrillic; a transliterated name is a wrong name on a document.
        # 503 with a stable code instead of a bare 500 (SD-07).
        from app.api.errors import ApiError

        raise ApiError(503, "unavailable", "PDF временно недоступен: на сервере нет шрифта с кириллицей")
    pdf.add_font("Body", "", str(font))
    pdf.set_font("Body", size=12)
    for line in lines:
        pdf.multi_cell(0, 8, line or " ")
        pdf.ln(1)
    out = pdf.output()
    return bytes(out) if not isinstance(out, bytes) else out
