"""Benjamini–Hochberg for the leak monitor. It is not the quarantine rule."""
from pathlib import Path

from app.services.item_monitor import MIN_N, Z_ALARM, KeyStats, bh_reject, one_sided_p

# Fifteen sorted p-values. At alpha 0.05 the largest passing rank is 4:
# p(4)=0.0095 ≤ 4/15·0.05, and p(5)=0.0201 is already above 5/15·0.05.
PUBLISHED = [
    0.0001, 0.0004, 0.0019, 0.0095, 0.0201, 0.0278, 0.0298, 0.0344,
    0.0459, 0.3240, 0.4262, 0.5719, 0.6528, 0.7590, 1.0,
]


def test_bh_matches_the_published_step_up():
    flags = bh_reject(PUBLISHED)
    assert flags == [True] * 4 + [False] * 11
    shuffled = list(reversed(PUBLISHED))
    assert bh_reject(shuffled) == list(reversed(flags))
    assert bh_reject([]) == []


def test_bh_does_not_replace_the_key_rule():
    # z = 3.5 is the product gate. Among a few hundred keys the first BH gate is tighter,
    # so the same signal would not be rejected. Quarantine still looks at one key.
    lone = KeyStats(n=MIN_N, correct=25, expected=15.0, variance=7.5)
    assert lone.z >= Z_ALARM and lone.alarm
    p = one_sided_p(lone.z)
    crowd = [p] + [0.5] * 399
    assert bh_reject(crowd)[0] is False
    blatant = [one_sided_p(8.0)] + [0.5] * 399
    assert bh_reject(blatant)[0] is True
    source = (Path(__file__).resolve().parents[2] / "app" / "services" / "assessment.py").read_text(encoding="utf-8")
    assert "st.alarm or st.cusum_alarm" in source
    assert "bh_reject" not in source
