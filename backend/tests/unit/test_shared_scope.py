"""Audit-5 A8: the shared need ranking is keyed by the company's exclusions, and a company with blocks gets none."""
import asyncio
import uuid

from app.services.exclusions import shared_scope


class _Db:
    def __init__(self, *answers):
        self.answers = list(answers)

    async def scalar(self, _stmt):
        return self.answers.pop(0)


def test_a_company_with_a_block_does_not_share():
    assert asyncio.run(shared_scope(_Db(uuid.uuid4()), uuid.uuid4(), None)) is None


def test_the_need_industry_wins_over_the_company_industry():
    assert asyncio.run(shared_scope(_Db(None), uuid.uuid4(), "fintech")) == "fintech"


def test_the_company_industry_is_used_when_the_need_has_none():
    assert asyncio.run(shared_scope(_Db(None, "fintech"), uuid.uuid4(), None)) == "fintech"


def test_no_industry_is_one_shared_scope():
    assert asyncio.run(shared_scope(_Db(None, None), uuid.uuid4(), "any")) == "-"
