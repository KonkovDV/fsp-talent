"""Runtime model provider: a fixed list of Russian hosts, a sealed key, no personal data, no internal addresses."""
import socket
import uuid
from datetime import UTC, datetime
from types import SimpleNamespace

import httpx
import pytest

from app.api.errors import ApiError
from app.api.v1 import moderation
from app.models import AiProvider
from app.models.ai_provider import open_secret
from app.services import totp
from app.services.ai import providers

PUBLIC = [(socket.AF_INET, socket.SOCK_STREAM, 6, "", ("213.180.193.1", 443))]
REAL_CLIENT = httpx.AsyncClient


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    providers.forget()
    monkeypatch.setattr(providers.settings, "AI_ENABLED", True)
    monkeypatch.setattr(providers.settings, "GIGACHAT_CREDENTIALS", "")
    yield
    providers.forget()


def test_only_listed_providers_and_clean_parameters_pass():
    assert providers.validate("yandex", "yandexgpt/latest", "yandexgpt-lite/latest",
                              {"folder_id": "b1gabc123"}, "AQVN-key") == {"folder_id": "b1gabc123"}
    assert providers.validate("gigachat", "GigaChat-2-Pro", None, {}, "key") == {"scope": "GIGACHAT_API_PERS"}
    for kind, model, check, params, secret, text in [
        ("openai", "gpt-4o", None, {}, "k", "нет в списке"),
        ("mws", "dep-1", None, {"project": "http://10.0.0.1/"}, "k", "project"),
        ("yandex", "yandexgpt/latest", None, {"folder_id": "../../admin"}, "k", "folder_id"),
        ("cloudru", "model?x=1", None, {}, "k", "Модель"),
        ("cloudru", "m", "m", {}, "k", "отличаться"),
        ("cloudru", "m", None, {}, "with space", "Ключ"),
        ("gigachat", "m", None, {"scope": "ANY"}, "k", "Scope"),
    ]:
        with pytest.raises(ValueError, match=text):
            providers.validate(kind, model, check, params, secret)


def test_requests_go_to_fixed_hosts_and_yandex_does_not_log():
    yandex = providers.Provider("yandex", "yandexgpt/latest", None, "KEY", {"folder_id": "b1g"})
    url, headers, model = providers.request_for(yandex, "yandexgpt/latest")
    assert url == "https://llm.api.cloud.yandex.net/v1/chat/completions"
    assert headers == {"Authorization": "Api-Key KEY", "x-data-logging-enabled": "false"}
    assert model == "gpt://b1g/yandexgpt/latest"
    mws = providers.Provider("mws", "dep", None, "KEY", {"project": "talent"})
    assert providers.request_for(mws, "dep")[0] == "https://gpt.mwsapis.ru/projects/talent/openai/v1/chat/completions"
    for provider in (yandex, mws, providers.Provider("cloudru", "m", None, "K")):
        assert httpx.URL(providers.request_for(provider, "m")[0]).host in providers.KINDS[provider.kind].hosts


def test_the_desk_choice_wins_over_the_environment_and_the_switch_turns_all_off(monkeypatch):
    assert providers.active() is None
    monkeypatch.setattr(providers.settings, "GIGACHAT_CREDENTIALS", "env-key")
    assert providers.active().source == "env"
    monkeypatch.setattr(providers, "_stored", providers.Provider("cloudru", "m", None, "k", source="db"))
    assert providers.active().kind == "cloudru"
    monkeypatch.setattr(providers.settings, "AI_ENABLED", False)
    assert providers.active() is None


def _capture(monkeypatch, answer=None):
    sent = {}

    def handler(request: httpx.Request) -> httpx.Response:
        sent["url"], sent["headers"], sent["body"] = str(request.url), request.headers, request.read().decode()
        return answer or httpx.Response(200, json={"choices": [{"message": {"content": "готово"}}]})

    def client(**kwargs):
        sent["follow_redirects"], sent["trust_env"] = kwargs.get("follow_redirects"), kwargs.get("trust_env")
        return REAL_CLIENT(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(providers.httpx, "AsyncClient", client)
    return sent


async def test_a_call_strips_contacts_and_refuses_redirects(monkeypatch):
    monkeypatch.setattr(providers.socket, "getaddrinfo", lambda *a, **k: PUBLIC)
    sent = _capture(monkeypatch)
    provider = providers.Provider("cloudru", "ai-sage/GigaChat3-10B-A1.8B", None, "KEY")
    reply = await providers.chat(provider, provider.model, "sys", "Пишите ivan@mail.ru или +7 913 000-00-00")
    assert reply == "готово" and sent["follow_redirects"] is False and sent["trust_env"] is False
    assert "ivan@mail.ru" not in sent["body"] and "913" not in sent["body"]
    assert sent["headers"]["authorization"] == "Bearer KEY"

    _capture(monkeypatch, httpx.Response(302, headers={"Location": "http://169.254.169.254/"}))
    with pytest.raises(providers.ProviderError, match="302"):
        await providers.chat(provider, provider.model, "sys", "text")


@pytest.mark.parametrize("address", ["10.0.0.5", "127.0.0.1", "169.254.169.254", "::1", "::ffff:192.168.1.1"])
async def test_a_host_that_resolves_inside_is_never_called(monkeypatch, address):
    family = socket.AF_INET6 if ":" in address else socket.AF_INET
    monkeypatch.setattr(providers.socket, "getaddrinfo",
                        lambda *a, **k: [(family, socket.SOCK_STREAM, 6, "", (address, 443))])
    sent = _capture(monkeypatch)
    with pytest.raises(providers.ProviderError, match="внутренний"):
        await providers.chat(providers.Provider("cloudru", "m", None, "K"), "m", "sys", "text")
    assert "url" not in sent


class Rows(list):
    pass


class Db:
    def __init__(self, employer):
        self.employer, self.rows, self.commits, self.executed = employer, [], 0, []

    async def get(self, model, ident, **kwargs):
        if model is moderation.Employer:
            return self.employer if ident == self.employer.id else None
        return next((r for r in self.rows if r.id == ident), None)

    async def scalars(self, stmt):
        return Rows(self.rows)

    async def scalar(self, stmt):
        return next((r for r in self.rows if r.is_active), None)

    async def execute(self, stmt):
        self.executed.append(stmt)
        for row in self.rows:
            row.is_active = False

    def add(self, row):
        self.rows.append(row)

    async def delete(self, row):
        self.rows.remove(row)

    async def commit(self):
        self.commits += 1


@pytest.fixture
def desk(monkeypatch):
    async def never(*args, **kwargs):
        return False
    monkeypatch.setattr(moderation, "too_many", never)
    monkeypatch.setattr(moderation.settings, "DEMO_MODE", True)
    eid = uuid.uuid4()
    sealed = totp.seal_secret(str(eid), totp.new_secret())
    employer = SimpleNamespace(id=eid, email="hr@sibcode.demo", totp_secret=sealed,
                               totp_last_step=None, totp_verified_at=datetime.now(UTC))
    return SimpleNamespace(db=Db(employer), current={"sub": str(eid)}, employer=employer)


BODY = moderation.ProviderIn(kind="yandex", label="Яндекс, прод", model="yandexgpt/latest",
                             check_model="yandexgpt-lite/latest", params={"folder_id": "b1gabc"}, secret="AQVN-secret")


async def test_the_key_is_sealed_never_shown_and_one_provider_is_active(desk):
    out = await moderation.add_provider(BODY, desk.current, desk.db)
    assert "AQVN-secret" not in str(out) and not out["is_active"]
    [row] = desk.db.rows
    assert row.secret.startswith("enc:v1:") and open_secret(row) == "AQVN-secret"
    on = await moderation.activate_provider(row.id, desk.current, desk.db)
    assert on["is_active"] and desk.db.executed
    listed = await moderation.list_providers(desk.current, desk.db)
    assert listed["in_use"] == {"source": "db", "kind": "yandex", "model": "yandexgpt/latest"}
    assert "AQVN-secret" not in str(listed) and {k["kind"] for k in listed["kinds"]} == set(providers.KINDS)
    await moderation.deactivate_providers(desk.current, desk.db)
    assert (await moderation.list_providers(desk.current, desk.db))["in_use"] is None


async def test_keys_change_only_under_the_second_factor(desk):
    desk.employer.totp_secret = None
    with pytest.raises(ApiError) as no_factor:
        await moderation.add_provider(BODY, desk.current, desk.db)
    assert no_factor.value.code == "totp_required"
    assert (await moderation.list_providers(desk.current, desk.db))["can_edit"] is False


async def test_a_bad_key_is_reported_without_echoing_the_answer(desk, monkeypatch):
    await moderation.add_provider(BODY, desk.current, desk.db)
    row = desk.db.rows[0]

    async def refused(*args, **kwargs):
        raise providers.ProviderError("llm.api.cloud.yandex.net ответил 401")
    monkeypatch.setattr(moderation.providers, "chat", refused)
    assert await moderation.check_provider(row.id, desk.current, desk.db) == {
        "ok": False, "reason": "llm.api.cloud.yandex.net ответил 401"}
    await moderation.delete_provider(row.id, desk.current, desk.db)
    assert desk.db.rows == [] and isinstance(row, AiProvider)
