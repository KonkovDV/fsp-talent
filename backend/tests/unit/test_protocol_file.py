from app.services.protocol_file import certificate_grade, parse_protocol_text


def test_a_protocol_line_is_kept_and_does_not_set_a_grade():
    rows = parse_protocol_text(
        "дисциплина;дата;место;всего;статус;название\n"
        "алгоритмическое;2024-06-01;3;120;региональные;Открытый кубок\n"
        "не дисциплина;2024-06-01;1;10;региональные;Пусто\n"
    )
    assert len(rows) == 1
    row = rows[0]
    assert row.discipline == "algorithmic"
    assert row.place == 3 and row.total_participants == 120
    assert row.competition_status == "regional"
    assert row.trust_level == "file_import"
    assert row.event_id.startswith("file-")
    assert not hasattr(row, "grade")


def test_a_certificate_letter_does_not_become_the_grade():
    assert certificate_grade("сертификат 20240115-1-M-004") == "middle"
    assert certificate_grade("20240115-1-S-001") == "senior"
    assert certificate_grade("нет номера") is None
    assessed = "junior"
    named = certificate_grade("20240115-1-S-001")
    assert named == "senior" and assessed == "junior"


def test_the_same_line_twice_is_one_event():
    text = "робототехника;2023;1;40;всероссийские;Финал\nробототехника;2023;1;40;всероссийские;Финал\n"
    assert len(parse_protocol_text(text)) == 1
