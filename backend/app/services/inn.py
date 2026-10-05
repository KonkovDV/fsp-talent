"""Checksum of a Russian taxpayer id (ИНН), the FNS algorithm. No network call."""
from __future__ import annotations


def _digit(inn: str, coeffs: list[int]) -> str:
    return str(sum(int(n) * c for n, c in zip(inn, coeffs, strict=True)) % 11 % 10)


def inn_is_valid(inn: str) -> bool:
    if not inn.isdigit():
        return False
    if len(inn) == 10:
        return inn[9] == _digit(inn[:9], [2, 4, 10, 3, 5, 9, 4, 6, 8])
    if len(inn) == 12:
        n11 = _digit(inn[:10], [7, 2, 4, 10, 3, 5, 9, 4, 6, 8])
        n12 = _digit(inn[:11], [3, 7, 2, 4, 10, 3, 5, 9, 4, 6, 8])
        return inn[10] == n11 and inn[11] == n12
    return False
