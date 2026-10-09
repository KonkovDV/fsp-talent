"""The complaint desk is only the demo stand and the printed employer account."""
from app.api.v1.moderation import may_moderate


def test_the_desk_stays_closed_outside_the_demo_and_for_other_accounts():
    assert may_moderate(True, "hr@sibcode.demo") is True
    assert may_moderate(False, "hr@sibcode.demo") is False
    assert may_moderate(True, "hr@other.demo") is False
