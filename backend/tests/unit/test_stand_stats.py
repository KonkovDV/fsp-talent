"""Landing totals: whole-stand aggregates only."""
from app.api.v1.public import stand_counts


def test_stand_counts_has_only_four_totals():
    out = stand_counts(703, 255, 40, 16)
    assert out == {"candidates": 703, "with_fsp": 255, "families": 40, "companies": 16}


def test_with_fsp_never_exceeds_candidates():
    assert stand_counts(3, 5, 1, 0)["with_fsp"] == 3


def test_route_is_registered():
    from app.api.v1.public import router
    assert any(getattr(r, "path", "") == "/public/stats" for r in router.routes)


async def test_endpoint_returns_counts_only():
    from app.api.v1 import public

    class Db:
        def __init__(self):
            self.values = iter([5, 2, 3])

        async def scalar(self, _stmt):
            return next(self.values)

    out = await public.stand_stats(Db())
    assert set(out) == {"candidates", "with_fsp", "families", "companies"}
    assert out["candidates"] == 5 and out["with_fsp"] == 2 and out["companies"] == 3
