"""A tenth of a point of coverage is the same published figure. Three tenths is not."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from doc_numbers import coverage_within  # noqa: E402


def test_a_tenth_of_a_point_is_the_same_coverage():
    assert coverage_within(66.2, 66.1)
    assert coverage_within(66.1, 66.1)
    assert coverage_within(65.9, 66.1)


def test_four_tenths_is_a_different_coverage():
    assert coverage_within(66.4, 66.1) is False
