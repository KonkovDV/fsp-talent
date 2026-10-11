"""The default stack must start on a host without an NVIDIA GPU.

`gpus: all` (or a device reservation) in docker-compose.yml makes Docker refuse the backend on such a
host ("could not select device driver"). The GPU lives in an opt-in override file.
"""
from __future__ import annotations

import re
from pathlib import Path

import pytest

REPO = Path(__file__).resolve().parents[3]
BASE = REPO / "docker-compose.yml"
GPU = REPO / "docker-compose.gpu.yml"

pytestmark = pytest.mark.skipif(not BASE.exists(), reason="compose files are outside the backend image")


def _code(text: str) -> str:
    return "\n".join(line.split("#", 1)[0] for line in text.splitlines())


def test_base_compose_requests_no_gpu():
    code = _code(BASE.read_text(encoding="utf-8"))
    assert not re.search(r"^\s*gpus\s*:", code, re.M)
    assert "capabilities" not in code and "driver: nvidia" not in code


def test_gpu_override_reserves_the_card_for_backend_only():
    code = _code(GPU.read_text(encoding="utf-8"))
    assert re.search(r"^services:\s*\n\s+backend:", code, re.M)
    assert "capabilities: [gpu]" in code and "driver: nvidia" in code
    assert len(re.findall(r"^  \w[\w-]*:\s*$", code, re.M)) == 1


def test_makefile_adds_the_override_only_on_request():
    make = (REPO / "Makefile").read_text(encoding="utf-8")
    assert "$(if $(GPU), -f docker-compose.yml -f docker-compose.gpu.yml,)" in make
