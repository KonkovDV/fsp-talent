"""Half a point of coverage (Python 3.12 vs 3.13, compilers present or not) is the same figure. More is not."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from doc_numbers import coverage_within  # noqa: E402


def test_a_tenth_of_a_point_is_the_same_coverage():
    assert coverage_within(66.2, 66.1)
    assert coverage_within(66.1, 66.1)
    assert coverage_within(65.9, 66.1)


def test_the_interpreter_gap_is_the_same_coverage():
    assert coverage_within(73.4, 73.0)  # audit-4 F-11: 3.13 with all compilers vs 3.12 in CI


def test_more_than_half_a_point_is_a_different_coverage():
    assert coverage_within(66.7, 66.1) is False


def test_every_mismatch_is_reported_in_one_run():
    import doc_numbers
    import pytest

    doc_numbers.PROBLEMS.clear()
    doc_numbers.require("abc", "1001", "README")
    doc_numbers.require("abc", "1002", "INSTALL")
    doc_numbers.require("abc", "abc", "README")
    assert len(doc_numbers.PROBLEMS) == 2
    with pytest.raises(SystemExit) as stop:
        doc_numbers.report_problems()
    assert "расхождений 2" in str(stop.value) and "1001" in str(stop.value) and "1002" in str(stop.value)
    doc_numbers.PROBLEMS.clear()
