"""The moderation desk is staff only. The printed demo employer is not staff (stand ST-UI-01)."""
import ast
import inspect
import uuid
from types import SimpleNamespace

import pytest

from app.api.errors import ApiError
from app.api.v1 import methodist, moderation
from app.core.config import settings


class _Db:
    def __init__(self, row):
        self.row = row

    async def get(self, model, key):
        return self.row


def _employer(**extra):
    base = dict(id=uuid.uuid4(), email="moderator@fsp.example", is_methodist=False,
                totp_secret=None, totp_verified_at=None)
    base.update(extra)
    return SimpleNamespace(**base)


def test_only_the_staff_flag_opens_the_desk():
    assert moderation.is_staff(_employer(is_methodist=True)) is True
    assert moderation.is_staff(_employer()) is False
    # An older seed flagged the printed HR login; the stand database still has that row.
    assert moderation.is_staff(_employer(is_methodist=True, email="hr@sibcode.demo")) is False
    assert moderation.is_staff(_employer(is_methodist=True, email="JURY1@demo.talent")) is False
    assert moderation.is_staff(SimpleNamespace(email="hr@sibcode.demo")) is False
    assert moderation.is_staff(None) is False


@pytest.mark.parametrize("guard", [moderation._desk, moderation._staff])
async def test_printed_demo_employer_is_refused_on_the_demo_stand(monkeypatch, guard):
    monkeypatch.setattr(settings, "DEMO_MODE", True)
    current = {"sub": str(uuid.uuid4()), "role": "employer"}
    with pytest.raises(ApiError) as refused:
        await guard(current, _Db(_employer(is_methodist=True, email="hr@sibcode.demo")))
    assert refused.value.status_code == 404
    staff = await guard(current, _Db(_employer(is_methodist=True)))
    assert staff.is_methodist is True


@pytest.mark.parametrize("module", [moderation, methodist])
def test_every_route_checks_staff_before_anything_else(module):
    tree = ast.parse(inspect.getsource(module))
    routes = [f for f in tree.body if isinstance(f, ast.AsyncFunctionDef)
              and any("router" in ast.unparse(d) for d in f.decorator_list)]
    assert routes
    for fn in routes:
        calls = {ast.unparse(n.func) for n in ast.walk(fn) if isinstance(n, ast.Call)}
        assert calls & {"_desk", "_staff", "_key_desk"}, fn.name


def test_the_seed_does_not_make_a_printed_login_staff():
    from seed import generate_seed
    assert "is_methodist" not in inspect.getsource(generate_seed)


async def test_staff_status_says_only_yes_or_no():
    from app.api.v1 import employer
    current = {"sub": str(uuid.uuid4()), "role": "employer"}
    assert await employer.staff_status(current, _Db(_employer())) == {"is_staff": False}
    assert await employer.staff_status(current, _Db(_employer(is_methodist=True))) == {"is_staff": True}
    assert await employer.staff_status(current, _Db(_employer(is_methodist=True, email="hr@sibcode.demo"))) == {
        "is_staff": False}
