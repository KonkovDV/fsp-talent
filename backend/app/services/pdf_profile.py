"""Resume text from an uploaded PDF, and a profile PDF the candidate can download.

The file is not stored: only the extracted text is parsed into skills. The profile PDF is built
in memory. Cyrillic needs a system font (DejaVu on Linux, Arial on Windows); without one the
text is written in Latin so the file is still a valid PDF.
"""
from __future__ import annotations

import io
from pathlib import Path

from pypdf import PdfReader

MAX_PDF_BYTES = 5_000_000
_FONTS = (
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
    Path(r"C:\Windows\Fonts\arial.ttf"),
)


def extract_pdf_text(data: bytes) -> str:
    if len(data) > MAX_PDF_BYTES or not data.startswith(b"%PDF"):
        raise ValueError("pdf")
    reader = PdfReader(io.BytesIO(data))
    if reader.is_encrypted:
        raise ValueError("pdf")
    text = "\n".join((page.extract_text() or "") for page in reader.pages)
    return text.strip()[:20000]


def _font() -> Path | None:
    return next((path for path in _FONTS if path.is_file()), None)


def _latin(text: str) -> str:
    pairs = {
        "а": "a", "б": "b", "в": "v", "г": "g", "д": "d", "е": "e", "ё": "e", "ж": "zh",
        "з": "z", "и": "i", "й": "y", "к": "k", "л": "l", "м": "m", "н": "n", "о": "o",
        "п": "p", "р": "r", "с": "s", "т": "t", "у": "u", "ф": "f", "х": "h", "ц": "ts",
        "ч": "ch", "ш": "sh", "щ": "sch", "ъ": "", "ы": "y", "ь": "", "э": "e", "ю": "yu",
        "я": "ya",
    }
    pairs.update({src.upper(): (dst[:1].upper() + dst[1:] if dst else "") for src, dst in list(pairs.items())})
    return text.translate(str.maketrans(pairs))


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
    if font is not None:
        pdf.add_font("Body", "", str(font))
        pdf.set_font("Body", size=12)
        body = lines
    else:
        pdf.set_font("Helvetica", size=12)
        body = [_latin(line) for line in lines]
    for line in body:
        pdf.multi_cell(0, 8, line or " ")
        pdf.ln(1)
    out = pdf.output()
    return bytes(out) if not isinstance(out, bytes) else out
