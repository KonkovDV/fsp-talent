"""Protocol lines from a file when the registry has no API. They do not set a grade.

A row needs a known discipline, a date or a year, a place and a field size.
The same line twice is one event id.
"""
from __future__ import annotations

import hashlib
import io
import re
import zipfile
from datetime import date
from xml.etree import ElementTree as ET

from app.services.fsp.mock import FSPResult

_NS = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
_DISC = (
    ("алгоритм", "algorithmic"),
    ("продуктов", "product"),
    ("систем иб", "security"),
    ("информационн", "security"),
    ("бас", "bas"),
    ("робот", "robotics"),
    ("искусствен", "ai"),
    ("систем ии", "ai"),
)
_STATUS = (
    ("мир", "world"),
    ("кубок росс", "russia_cup"),
    ("первенств", "russia_youth"),
    ("чемпионат росс", "russia_championship"),
    ("всеросс", "all_russian"),
    ("федеральн", "federal_district"),
    ("субъект", "regional"),
    ("регион", "regional"),
)


def _discipline(text: str) -> str | None:
    folded = text.casefold()
    for stem, code in _DISC:
        if stem in folded:
            return code
    return None


def _status(text: str) -> str:
    folded = text.casefold()
    for stem, code in _STATUS:
        if stem in folded:
            return code
    return "other"


def _date(text: str) -> date | None:
    if match := re.fullmatch(r"(\d{4})-(\d{2})-(\d{2})", text):
        try:
            return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))
        except ValueError:
            return None
    if re.fullmatch(r"20\d{2}", text):
        return date(int(text), 1, 1)
    return None


_CERT_GRADE = {"J": "junior", "M": "middle", "S": "senior"}


def certificate_grade(text: str) -> str | None:
    """The letter in a certificate number. It is not a grade and is not written into one."""
    match = re.search(r"\d{8}-\d+-([JMSjms])-\d+", text or "")
    if not match:
        return None
    return _CERT_GRADE[match.group(1).upper()]


def parse_protocol_text(text: str) -> list[FSPResult]:
    found: list[FSPResult] = []
    seen: set[str] = set()
    for raw in text.splitlines():
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        parts = [part.strip() for part in re.split(r"[;\t|]", line) if part.strip()]
        if len(parts) < 4:
            continue
        discipline = _discipline(parts[0])
        when = _date(parts[1])
        if discipline is None or when is None:
            continue
        if not parts[2].isdigit() or not parts[3].isdigit():
            continue
        place, total = int(parts[2]), int(parts[3])
        if place < 1 or total < place or total > 100_000:
            continue
        status = _status(parts[4]) if len(parts) > 4 else "other"
        name = parts[5] if len(parts) > 5 else "Протокол из файла"
        key = f"{discipline}|{when.isoformat()}|{place}|{total}|{name.casefold()}"
        event_id = "file-" + hashlib.sha256(key.encode()).hexdigest()[:16]
        if event_id in seen:
            continue
        seen.add(event_id)
        found.append(FSPResult(
            event_id=event_id, event_name=name[:300], discipline=discipline,
            competition_status=status, place=place, total_participants=total,
            is_team=False, team_size=1, event_date=when, trust_level="file_import",
        ))
        if len(found) == 40:
            break
    return found


def text_of_pdf(raw: bytes) -> str:
    from pypdf import PdfReader

    reader = PdfReader(io.BytesIO(raw))
    return "\n".join((page.extract_text() or "") for page in reader.pages[:20])


def text_of_xlsx(raw: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(raw)) as book:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in book.namelist():
            root = ET.fromstring(book.read("xl/sharedStrings.xml"))
            for item in root.findall("m:si", _NS):
                shared.append("".join(node.text or "" for node in item.iter(f"{{{_NS['m']}}}t")))
        sheets = [name for name in book.namelist() if name.startswith("xl/worksheets/sheet")]
        if not sheets:
            return ""
        root = ET.fromstring(book.read(sheets[0]))
        lines = []
        for row in root.findall("m:sheetData/m:row", _NS):
            cells = []
            for cell in row.findall("m:c", _NS):
                value = cell.find("m:v", _NS)
                if value is None or value.text is None:
                    cells.append("")
                elif cell.get("t") == "s" and value.text.isdigit():
                    cells.append(shared[int(value.text)])
                else:
                    cells.append(value.text)
            if any(cells):
                lines.append(";".join(cells))
        return "\n".join(lines)
