from app.services.search.pipeline import visible_card

WHY = ["Навыки: 1 из 1", "Присвоенный разряд КМС (алгоритмы)", "Подтверждено ФСП: алгоритмы, событий 2"]


def test_switches_drop_the_card_lines_and_leave_the_rest():
    stack, years, disciplines, why = visible_card(
        ["Python"], 4, [{"label": "алгоритмы"}], WHY, show_stack=False, show_fsp=False, show_experience=False)
    assert stack == [] and years is None and disciplines == []
    assert why == ["Навыки: 1 из 1"]


def test_defaults_keep_everything():
    stack, years, disciplines, why = visible_card(
        ["Python"], 4, [{"label": "алгоритмы"}], WHY, show_stack=True, show_fsp=True, show_experience=True)
    assert stack == ["Python"] and years == 4 and disciplines and why == WHY
