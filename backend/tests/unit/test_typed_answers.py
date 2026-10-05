"""A code item with a whole-number answer is typed; the comparison ignores spaces and the unicode minus."""
from app.items import CHOICE_C, TYPED_C, Item, same_number, typed_answer
from app.items.registry import FAMILIES, expected_guess, typed_share


def _item(options: list[str], correct: int = 0) -> Item:
    return Item(stem="Что выведет код?", options=options, correct=correct, explanation="")


def test_whole_number_code_is_typed_and_the_rest_keeps_options():
    assert typed_answer("code", _item(["11", "5", "6", "12"])) == "11"
    assert typed_answer("code", _item(["-48", "80", "48", "208"])) == "-48"
    assert typed_answer("code", _item(["0x2E", "46", "2E", "0x2F"])) is None
    assert typed_answer("code", _item(["3.5", "3", "4", "2"])) is None
    assert typed_answer("concept", _item(["11", "5", "6", "12"])) is None


def test_same_number_accepts_sign_spaces_and_rejects_the_rest():
    assert same_number(" 42 ", "42")
    assert same_number("+42", "42")
    assert same_number("\u221242", "-42")
    assert same_number("1\u00a0000", "1000")
    assert not same_number("42", "43")
    assert not same_number("4.0", "4")
    assert not same_number("", "0")
    assert not same_number("1234567890123", "1234567890123")


def test_expected_guess_follows_the_typed_share():
    for fam in FAMILIES.values():
        for level in fam.levels:
            share = typed_share(fam.id, level)
            guess = expected_guess(fam.id, level)
            assert 0.0 <= share <= 1.0
            assert guess == share * TYPED_C + (1.0 - share) * CHOICE_C
            if fam.kind != "code":
                assert share == 0.0
