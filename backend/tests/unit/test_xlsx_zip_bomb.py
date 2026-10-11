"""AUD-01: an xlsx protocol that unpacks into hundreds of MB is refused before it is read."""
import io
import tracemalloc
import zipfile

import pytest

from app.services.protocol_file import UnsafeArchive, text_of_xlsx


def _book(sheet: bytes) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        z.writestr("xl/worksheets/sheet1.xml", sheet)
    return buf.getvalue()


def test_a_zip_bomb_is_refused_without_unpacking():
    bomb = _book(b" " * 60_000_000)
    assert len(bomb) < 2_000_000  # fits the upload limit
    tracemalloc.start()
    with pytest.raises(UnsafeArchive):
        text_of_xlsx(bomb)
    _, peak = tracemalloc.get_traced_memory()
    tracemalloc.stop()
    assert peak < 20_000_000


def test_a_normal_sheet_still_reads():
    xml = (b'<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><sheetData>'
           b'<row><c t="inlineStr"><v>1</v></c></row></sheetData></worksheet>')
    assert isinstance(text_of_xlsx(_book(xml)), str)
