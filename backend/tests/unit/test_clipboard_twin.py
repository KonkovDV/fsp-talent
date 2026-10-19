from app.services.clipboard_twin import copy_text, one_number_twin, twin_hit


def test_the_copy_changes_one_number_and_keeps_the_rest():
    source = "В массиве 12 элементов, порог 40."
    twin, old, new = one_number_twin(source, "item-1")
    assert twin != source
    assert old in source and new not in source.split(old)
    assert twin.count(new) == 1
    assert one_number_twin(source, "item-1")[0] == twin


def test_the_hidden_number_is_a_mark_only_when_it_is_not_the_key():
    stem = "Сколько элементов больше 40?"
    assert twin_hit(stem, None, "item-1", "41", "3") or twin_hit(stem, None, "item-1", "39", "3")
    shown = one_number_twin(stem, "item-1")
    assert shown is not None
    _twin, _old, new = shown
    assert twin_hit(stem, None, "item-1", new, "3") is True
    assert twin_hit(stem, None, "item-1", "3", "3") is False
    assert copy_text("без чисел", None, "item-1") is None


def test_the_hidden_number_is_not_the_answer_key():
    shown = one_number_twin("Порог 4.", "s5", "5")
    assert shown is not None
    _twin, old, new = shown
    assert old == "4" and new != "5" and new != "4"
    assert "5" not in copy_text("Порог 4.", None, "s5", "5")
