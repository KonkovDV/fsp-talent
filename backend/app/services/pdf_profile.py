"""Resume text from an uploaded PDF, and a profile PDF the candidate can download.

The file is not stored: only the extracted text is parsed into skills. The profile PDF is built
in memory. Cyrillic needs a TrueType font with Cyrillic glyphs: the backend image installs
`fonts-dejavu-core` (backend/Dockerfile); a local run finds DejaVu or Liberation on Linux and Arial on
Windows or macOS. Names are never transliterated: without such a font the PDF is refused loudly.
"""
from __future__ import annotations

import io
from pathlib import Path

from pypdf import PdfReader

MAX_PDF_BYTES = 5_000_000
MAX_PDF_PAGES = 30
_FONTS = (
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/truetype/liberation/LiberationSans-Regular.ttf"),
    Path(r"C:\Windows\Fonts\arial.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    Path("/Library/Fonts/Arial.ttf"),
)


def extract_pdf_text(data: bytes) -> str:
    if len(data) > MAX_PDF_BYTES or not data.startswith(b"%PDF"):
        raise ValueError("pdf")
    try:
        reader = PdfReader(io.BytesIO(data))
        if reader.is_encrypted:
            raise ValueError("pdf")
        pages = list(reader.pages)[:MAX_PDF_PAGES]
        text = "\n".join((page.extract_text() or "") for page in pages)
    except ValueError:
        raise
    except Exception as exc:
        raise ValueError("pdf") from exc
    return text.strip()[:20000]


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
