"""The method page publishes a share, never a stem or an answer key."""
import pytest

from app.api.v1.public import _without_keys, curve_cache_key, exposure_cache_key


def test_exposure_is_cached_once_for_the_whole_bank():
    assert "backend" not in exposure_cache_key()
    assert exposure_cache_key() == exposure_cache_key()
    assert curve_cache_key("backend") != curve_cache_key("frontend")


def test_method_payload_keeps_the_max_share():
    payload = _without_keys({"spec": "backend", "max_share": 0.34, "answers": 10, "families": []})
    assert payload["max_share"] == 0.34


@pytest.mark.parametrize("key", ["item_key", "stem", "answer"])
def test_method_payload_rejects_a_key(key):
    with pytest.raises(RuntimeError):
        _without_keys({"families": [{key: "скрыто"}]})
