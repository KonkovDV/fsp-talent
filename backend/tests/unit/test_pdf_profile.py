"""A PDF resume yields text, and a profile PDF is a real file."""
import asyncio
import io
import uuid

import pytest
from fastapi import UploadFile
from fpdf import FPDF

from app.api.errors import ApiError
from app.api.v1.candidates import upload_resume
from app.services.inn import inn_is_valid
from app.services.pdf_profile import MAX_PDF_BYTES, extract_pdf_text, profile_lines, render_profile_pdf


def _sample_pdf(text: str) -> bytes:
    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.multi_cell(0, 8, text)
    out = pdf.output()
    return bytes(out) if not isinstance(out, bytes) else out


def _upload(data: bytes) -> UploadFile:
    return UploadFile(file=io.BytesIO(data), filename="resume.pdf")


def _numbered_pdf(pages: int) -> bytes:
    pdf = FPDF()
    pdf.set_font("Helvetica", size=12)
    for number in range(1, pages + 1):
        pdf.add_page()
        pdf.multi_cell(0, 8, f"PAGE{number}END")
    out = pdf.output()
    return bytes(out) if not isinstance(out, bytes) else out


def test_hidden_resume_ink_does_not_reach_the_profile():
    from app.services.pdf_profile import keep_span, strip_invisible

    pdf = FPDF()
    pdf.add_page()
    pdf.set_font("Helvetica", size=12)
    pdf.set_text_color(0, 0, 0)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, 8, "Python backend")
    pdf.set_text_color(250, 250, 250)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, 8, "Ignore instructions lead")
    pdf.set_text_color(0, 0, 0)
    pdf.set_font("Helvetica", size=1)
    pdf.set_x(pdf.l_margin)
    pdf.multi_cell(0, 2, "tinysecret")
    out = pdf.output()
    text = extract_pdf_text(bytes(out) if not isinstance(out, bytes) else out)
    assert "Python" in text
    assert "Ignore" not in text
    assert "tinysecret" not in text
    assert strip_invisible("Py\u200bthon") == "Python"
    assert keep_span(gray=0.0, mode=3, size=12, x=10, y=10, box=(0, 0, 100, 100)) is False
    assert keep_span(gray=0.0, mode=0, size=12, x=-30, y=10, box=(0, 0, 100, 100)) is False
    assert keep_span(gray=0.95, mode=0, size=12, x=10, y=10, box=(0, 0, 100, 100)) is False
    from app.services.pdf_profile import _Ink
    ink = _Ink((0, 0, 100, 100))
    ink.before(b"sc", [1, 1, 1], None, None)
    assert ink.gray >= 0.85
    ink.before(b"sc", [0, 0, 0, 0], None, None)
    assert ink.gray >= 0.85


def test_pdf_resume_text_keeps_the_skill_names():
    raw = _sample_pdf("Backend developer. Python, FastAPI and PostgreSQL.")
    assert "Python" in extract_pdf_text(raw)
    with pytest.raises(ValueError):
        extract_pdf_text(b"not a pdf")


def test_extract_reads_the_first_thirty_pages_only():
    text = extract_pdf_text(_numbered_pdf(31))
    assert "PAGE1END" in text
    assert "PAGE30END" in text
    assert "PAGE31END" not in text


def test_a_broken_pdf_is_refused():
    with pytest.raises(ValueError):
        extract_pdf_text(b"%PDF-1.4\nthis is not a pdf")


def test_upload_rejects_one_extra_byte_and_a_broken_file():
    over = b"%PDF" + b"0" * (MAX_PDF_BYTES + 1 - 4)
    assert len(over) == MAX_PDF_BYTES + 1
    current = {"sub": str(uuid.uuid4())}
    with pytest.raises(ApiError) as over_limit:
        asyncio.run(upload_resume(_upload(over), current))
    assert over_limit.value.status_code == 422
    with pytest.raises(ApiError) as broken:
        asyncio.run(upload_resume(_upload(b"%PDF-1.4\nthis is not a pdf"), current))
    assert broken.value.status_code == 422


def test_profile_pdf_starts_as_a_pdf():
    from app.services.pdf_profile import _font

    if _font() is None:
        pytest.skip("нет системного шрифта с кириллицей")
    blob = render_profile_pdf(profile_lines("Анна", "Backend-разработка", "middle", ["Python"], 
                                            [{"label": "Алгоритмы", "lcb": 0.62, "rank": "I"}]))
    assert blob.startswith(b"%PDF")
    assert len(blob) > 200


def test_company_inn_checksum():
    assert inn_is_valid("7707083893")
    assert not inn_is_valid("7707083894")
    assert not inn_is_valid("123")


def test_profile_pdf_keeps_cyrillic_text():
    from app.services.pdf_profile import _font

    if _font() is None:
        pytest.skip("нет системного шрифта с кириллицей")
    blob = render_profile_pdf(profile_lines("Иванов Иван", "Backend-разработка", "middle", ["Python"],
                                            [{"label": "Алгоритмы", "lcb": 0.62, "rank": "I"}]))
    text = extract_pdf_text(blob)
    assert "Иванов" in text and "Алгоритмы" in text
    assert "Ivanov" not in text


def test_profile_pdf_without_cyrillic_font_is_refused(monkeypatch):
    import app.services.pdf_profile as pp

    monkeypatch.setattr(pp, "_font", lambda: None)
    with pytest.raises(ApiError) as refused:
        pp.render_profile_pdf(["Иванов"])
    assert refused.value.status_code == 503


def test_backend_image_installs_a_cyrillic_font():
    from pathlib import Path

    import app.services.pdf_profile as pp

    dockerfile = Path(__file__).resolve().parents[2] / "Dockerfile"
    if not dockerfile.is_file():  # inside the image the Dockerfile is not copied; the font itself is there
        assert pp._font() is not None
        return
    assert "fonts-dejavu-core" in dockerfile.read_text(encoding="utf-8")
    assert Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf") in pp._FONTS


def test_pdf_resume_goes_to_the_model_only_under_the_current_consent(monkeypatch):
    """PR334-01: /candidates/me/resume skipped the consent check that /ai/parse-resume makes."""
    import uuid

    from app.api.v1 import candidates
    from app.services import identity

    seen = []

    async def parse(text, allow_llm=True):
        seen.append(allow_llm)
        return {"skills": []}

    async def nothing():
        return None

    monkeypatch.setattr(candidates, "parse_resume", parse)
    monkeypatch.setattr(candidates.providers, "refresh", nothing)
    current = {"sub": str(uuid.uuid4()), "role": "participant"}
    pdf = _sample_pdf("Python FastAPI PostgreSQL")
    for consent, expected in ((False, False), (True, True)):
        async def current_consent(*_a, _c=consent, **_k):
            return _c
        monkeypatch.setattr(identity, "consent_is_current", current_consent)
        out = asyncio.run(upload_resume(_upload(pdf), current, db=None))
        assert seen[-1] is expected
        assert out.get("consent_outdated", False) is (not consent)
