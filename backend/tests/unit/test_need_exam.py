"""A need forms a test the same way a vacancy does: its skills pull the topic mix, keys never leave."""
from app.services.vacancy_exam import form_exam


def test_need_skills_pull_the_mix_and_no_keys_leak():
    plain = form_exam("Backend-разработчик", "", [], "backend", "middle")
    sql = form_exam("Backend-разработчик", "", ["PostgreSQL", "ClickHouse"], "backend", "middle")
    share = {t["topic"]: t["share"] for t in sql["topics"]}
    base = {t["topic"]: t["share"] for t in plain["topics"]}
    assert share["sql"] > base.get("sql", 0)
    assert abs(sum(share.values()) - 1) < 0.01
    for sample in sql["samples"]:
        assert set(sample) == {"topic", "topic_label", "family", "stem", "code", "language"}
