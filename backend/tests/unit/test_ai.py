"""Unit tests for AI assistant query parsing (no LLM required)."""
from app.services.ai.assistant import _word_hit


def test_cyrillic_stem_matches_inflected_forms():
    """Cyrillic-ending tokens are treated as morphological stems (no right boundary)."""
    assert _word_hit("алгоритмическое программирование", ("алгоритм",))
    assert _word_hit("олимпиадное программирование", ("олимпиад",))
    assert _word_hit("задачи по безопасности", ("безопасност",))
    assert _word_hit("пентестер", ("пентест",))


def test_ascii_word_requires_full_word_match():
    """ASCII words must be delimited on both sides — no false prefix/suffix matches."""
    # true positives
    assert _word_hit("security audit", ("security",))
    assert _word_hit("backend developer", ("backend",))
    assert _word_hit("frontend engineer", ("frontend",))
    # false positives that the old len-heuristic allowed
    assert not _word_hit("insecurity", ("security",))
    assert not _word_hit("cybersecurity", ("security",))
    assert not _word_hit("backendservice", ("backend",))
    assert not _word_hit("myfrontend", ("frontend",))


def test_short_ascii_also_gets_right_boundary():
    """Short abbreviations (ctf, sre, ios …) must not match mid-word."""
    assert _word_hit("ctf writeup", ("ctf",))
    assert not _word_hit("noctf", ("ctf",))
    assert _word_hit("sre team", ("sre",))
    assert not _word_hit("sremote", ("sre",))
    assert _word_hit("ios developer", ("ios",))
    assert not _word_hit("bios", ("ios",))


def test_mixed_query_parses_correctly():
    """Realistic query: all tokens detected, no cross-contamination."""
    low = "сеньор бэкенд python ctf"
    assert _word_hit(low, ("senior", "сеньор", "синьор"))
    assert _word_hit(low, ("backend", "бэкенд", "бекенд"))
    assert _word_hit(low, ("ctf",))
    # 'security' role keyword must NOT fire on the word 'ctf'
    assert not _word_hit(low, ("security",))
