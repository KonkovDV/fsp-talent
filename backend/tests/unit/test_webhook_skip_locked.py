"""RT-07: due deliveries are claimed with FOR UPDATE SKIP LOCKED, so a parallel pass skips them."""
import asyncio

from sqlalchemy.dialects import postgresql

from app.services.webhooks import deliver_due


class _Db:
    def __init__(self):
        self.sql = []

    async def scalars(self, query):
        self.sql.append(str(query.compile(dialect=postgresql.dialect())))
        return []


def test_due_rows_are_claimed_skip_locked():
    db = _Db()
    asyncio.run(deliver_due(db))
    assert "FOR UPDATE OF webhook_deliveries SKIP LOCKED" in db.sql[0]


def test_employer_pass_also_skips_locked():
    import uuid
    db = _Db()
    asyncio.run(deliver_due(db, uuid.uuid4()))
    assert "SKIP LOCKED" in db.sql[0]
