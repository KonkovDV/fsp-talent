import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "load_api", Path(__file__).resolve().parents[1] / "load_api.py")
load_api = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(load_api)
single_winner = load_api.single_winner


def test_one_success_and_conflicts_count_as_a_single_winner():
    assert single_winner([200, 409, 409])
    assert not single_winner([200, 200])
    assert not single_winner([409, 409])
    assert not single_winner([200, 500])
