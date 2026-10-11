"""The simulated test can carry measurement error; the default benchmark stays noiseless and unchanged."""
import json

from app.validation import matching as V


def _digest(data: dict) -> str:
    return json.dumps(data, sort_keys=True, default=str)


def test_default_dataset_is_unchanged_by_the_noise_stream():
    assert V.TEST_NOISE_SD == 0.0
    a = V.make_dataset(120, 12, 2026)
    b = V.make_dataset(120, 12, 2026)
    assert _digest(a) == _digest(b)


def test_noise_changes_only_test_probabilities():
    base = V.make_dataset(120, 12, 2026)
    V.TEST_NOISE_SD = 0.47
    try:
        noisy = V.make_dataset(120, 12, 2026)
    finally:
        V.TEST_NOISE_SD = 0.0
    assert [c["truth"] for c in base["candidates"]] == [c["truth"] for c in noisy["candidates"]]
    assert base["labels"] == noisy["labels"]
    tested = [(x["observed"].get("test_p"), y["observed"].get("test_p"))
              for x, y in zip(base["candidates"], noisy["candidates"])]
    assert any(p != q for p, q in tested)
