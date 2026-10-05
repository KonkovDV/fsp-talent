"""A PDF resume yields text, and a profile PDF is a real file."""
from fpdf import FPDF

from app.services.inn import inn_is_valid
from app.services.pdf_profile import extract_pdf_text, profile_lines, render_profile_pdf


def _sample_pdf(text: str) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, 8, text)
    out = pdf.output()
    return bytes(out) if not isinstance(out, bytes) else out


def test_pdf_resume_text_keeps_the_skill_names():
    raw = _sample_pdf("Backend developer. Python, FastAPI and PostgreSQL.")
    assert "Python" in extract_pdf_text(raw)
    try:
        extract_pdf_text(b"not a pdf")
        raised = False
    except ValueError:
        raised = True
    assert raised


def test_profile_pdf_starts_as_a_pdf():
    blob = render_profile_pdf(profile_lines("Анна", "Backend-разработка", "middle", ["Python"], 
                                            [{"label": "Алгоритмы", "lcb": 0.62, "rank": "I"}]))
    assert blob.startswith(b"%PDF")
    assert len(blob) > 200


def test_company_inn_checksum():
    assert inn_is_valid("7707083893")
    assert not inn_is_valid("7707083894")
    assert not inn_is_valid("123")
