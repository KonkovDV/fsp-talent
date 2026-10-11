from pathlib import Path

from app.validation.accept import CHECKS, missing_nodes

TRACE = Path(__file__).resolve().parents[3] / "docs" / "requirements_trace.md"


def test_every_acceptance_row_names_a_real_test_and_the_trace():
    assert not missing_nodes()
    text = TRACE.read_text(encoding="utf-8")
    codes = [code for code, _title, _node in CHECKS]
    expected = [f"FR-{n:02d}" for n in range(1, 14)] + [f"NFR-{n:02d}" for n in range(1, 11)]
    expected += ["TC-01", "TC-02"] + [f"AUD-{n:02d}" for n in range(1, 14)]
    assert codes == expected
    for code, _title, node in CHECKS:
        assert f"| {code} |" in text
        assert node.split("::", 1)[1] in text
