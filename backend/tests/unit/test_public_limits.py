from app.api.v1.public import limits
from app.core.config import settings


async def test_limits_serve_the_backend_floor():
    assert await limits() == {"min_monthly_gross": settings.MIN_MONTHLY_GROSS} and settings.MIN_MONTHLY_GROSS == 27_093
