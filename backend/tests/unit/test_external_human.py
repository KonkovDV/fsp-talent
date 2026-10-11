"""External human-ranked matching check: parsing, statistics and the hash guard, without network."""
from __future__ import annotations

import hashlib
import io
import zipfile

import pytest

from app.validation import external_human as eh

ANN = """ANNOTATOR_1_RANKINGS=[[1,2,3,4,5],[2,1,3,4,5],[1,1,3,4,5]]
ANNOTATOR_2_RANKINGS= [[1,2,3,5,4], [2,1,4,3,5], [5,4,3,2,1]]
"""


def _docx(text: str) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("word/document.xml", f"<w:document><w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p>"
                   "<w:p><w:r><w:t>Python &amp; SQL</w:t></w:r></w:p></w:body></w:document>")
    return buf.getvalue()


def test_parse_annotations_positions_are_vacancies(monkeypatch):
    monkeypatch.setattr(eh, "RESUMES", 3)
    a1, a2 = eh.parse_annotations(ANN)
    assert a1[2] == [1, 1, 3, 4, 5]          # a tie stays a tie
    assert a2[2] == [5, 4, 3, 2, 1]


def test_docx_text_reads_paragraphs():
    assert eh.docx_text(_docx("Java developer")).splitlines() == ["Java developer", "Python & SQL"]


def test_rank_statistics():
    assert eh.spearman([1, 2, 3], [1, 2, 3]) == pytest.approx(1.0)
    assert eh.kendall_tau_b([1, 2, 3, 4], [4, 3, 2, 1]) == pytest.approx(-1.0)
    assert eh.kendall_tau_b([1, 1, 1], [1, 2, 3]) is None
    assert eh.ndcg([0, 1, 2], [3, 2, 1]) == pytest.approx(1.0)
    assert eh.ndcg([2, 1, 0], [3, 2, 1]) < 1.0


def test_evaluate_perfect_and_agreement(monkeypatch):
    monkeypatch.setattr(eh, "RESUMES", 3)
    a1, a2 = eh.parse_annotations(ANN)
    perfect = [[-(x + y) / 2 for x, y in zip(r1, r2, strict=True)] for r1, r2 in zip(a1, a2, strict=True)]
    r = eh.evaluate(perfect, a1, a2)
    assert r["tau"] == pytest.approx(1.0) and r["ndcg5"] == pytest.approx(1.0) and r["top1"] == 1.0
    assert eh.annotator_agreement(a1, a1)["tau"] == pytest.approx(1.0)


def test_fetch_rejects_wrong_hash(tmp_path, monkeypatch):
    good = b"vacancies"
    monkeypatch.setattr(eh, "SHA256", {"a.csv": hashlib.sha256(good).hexdigest()})
    assert eh.fetch(tmp_path, opener=lambda url: good) == tmp_path
    assert (tmp_path / "a.csv").read_bytes() == good
    (tmp_path / "a.csv").unlink()
    with pytest.raises(eh.DatasetError):
        eh.fetch(tmp_path, opener=lambda url: b"tampered")
    assert not (tmp_path / "a.csv").exists()


def test_fetch_without_network_is_a_clear_error(tmp_path, monkeypatch):
    monkeypatch.setattr(eh, "SHA256", {"a.csv": "0" * 64})

    def offline(url: str) -> bytes:
        raise OSError("network is unreachable")
    with pytest.raises(eh.DatasetError, match="нет доступа"):
        eh.fetch(tmp_path, opener=offline)


def test_pinned_commit_and_hashes():
    assert len(eh.COMMIT) == 40
    assert len(eh.SHA256) == 2 + eh.RESUMES
    assert all(len(h) == 64 for h in eh.SHA256.values())
