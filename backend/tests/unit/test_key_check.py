"""The key re-run report counts matches honestly and flags a wrong key."""
from app.validation import key_check


def test_small_run_matches_every_key():
    result = key_check.check(variants=1, families=["py_eval", "sql_query"])
    for tally in result.values():
        assert tally.checked > 0
        assert tally.matched == tally.checked
    text = key_check.markdown(result, 1, 2026)
    assert "Итого: исполнено" in text and "py_eval" in text


def test_wrong_key_is_not_counted_as_a_match():
    verify = {"runner": "python", "code": "print(2 + 2)", "expect": "5"}
    assert not key_check.matches(verify, key_check.run(verify))
    verify["expect"] = "4"
    assert key_check.matches(verify, key_check.run(verify))


def test_unknown_runner_is_not_checked():
    try:
        key_check.run({"runner": "cobol"})
    except key_check.NotAvailable:
        return
    raise AssertionError("an unknown runner must not count as checked")
