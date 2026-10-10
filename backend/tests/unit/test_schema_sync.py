import re

from app.core.schema_sync import Catalog, _split_body, plan, schema_statements


def _full() -> Catalog:
    """The catalog a fresh upgrade leaves behind, read from the same SQL."""
    have = Catalog()
    for stmt in schema_statements():
        if m := re.match(r"CREATE TABLE public\.(\w+) \(", stmt):
            have.tables.add(m.group(1))
            body = stmt[stmt.index("(") + 1:stmt.rindex(")")]
            for item in _split_body(body):
                if item.startswith("CONSTRAINT "):
                    have.constraints.add(item.split()[1])
                else:
                    have.columns.setdefault(m.group(1), set()).add(item.split()[0].strip('"'))
        elif m := re.match(r"CREATE (?:UNIQUE )?INDEX (\w+)", stmt):
            have.indexes.add(m.group(1))
        elif m := re.match(r"ALTER TABLE (?:ONLY )?public\.\w+\s+ADD CONSTRAINT (\w+)", stmt):
            have.constraints.add(m.group(1))
        elif m := re.match(r"CREATE POLICY (\w+)", stmt):
            have.policies.add(m.group(1))
    return have


def test_a_current_database_needs_nothing():
    assert plan(schema_statements(), _full()) == []


def test_an_old_database_gets_only_what_it_lacks_and_nothing_is_dropped():
    have = _full()
    have.tables.discard("item_drafts")
    have.indexes.discard("ix_item_drafts_status")
    have.columns["participants"] -= {"show_city", "last_login_at"}
    have.policies.discard("complaints_actor")
    todo = plan(schema_statements(), have)
    assert todo[0].startswith("CREATE TABLE public.item_drafts (")
    assert "ALTER TABLE public.participants ADD COLUMN IF NOT EXISTS show_city boolean DEFAULT true NOT NULL" in todo
    assert any(s.startswith("ALTER TABLE public.participants ADD COLUMN IF NOT EXISTS last_login_at") for s in todo)
    assert any(s.startswith("CREATE INDEX ix_item_drafts_status") for s in todo)
    assert any(s.startswith("CREATE POLICY complaints_actor") for s in todo)
    assert len(todo) == 5
    assert not any(word in s.upper() for s in todo for word in ("DROP ", "ALTER COLUMN", "TRUNCATE", "DELETE "))


def test_a_new_table_brings_its_row_level_security():
    have = _full()
    have.tables.discard("complaints")
    have.columns.pop("complaints")
    have.policies.discard("complaints_actor")
    have.indexes.discard("ix_complaints_participant_id")
    todo = plan(schema_statements(), have)
    assert todo[0].startswith("CREATE TABLE public.complaints (")
    assert "ALTER TABLE public.complaints ENABLE ROW LEVEL SECURITY" in todo
    assert any(s.startswith("CREATE POLICY complaints_actor") for s in todo)
