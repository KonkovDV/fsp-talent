"""Unit tests for AI assistant query parsing (no LLM or DB required)."""
from app.services.ai.assistant import _word_hit


# ---------------------------------------------------------------------------
# Stem matching: long Cyrillic tokens (len > 4, ends in Cyrillic)
# ---------------------------------------------------------------------------

def test_long_cyrillic_stem_matches_inflected_forms():
    """Tokens with len > 4 and Cyrillic ending are treated as morphological stems."""
    assert _word_hit("алгоритмическое программирование", ("алгоритм",))   # 8 chars
    assert _word_hit("олимпиадное программирование", ("олимпиад",))   # 8 chars
    assert _word_hit("задачи по безопасности", ("безопасност",))       # 11 chars
    assert _word_hit("роботехника", ("робот",))                       # 5 chars -> stem
    assert _word_hit("машинное обучение", ("машинн",))             # 6 chars
    assert _word_hit("беспилотник", ("беспилот",))                    # 8 chars
    assert _word_hit("кибербезопасность", ("кибербез",))           # 8 chars


# ---------------------------------------------------------------------------
# Boundary: short Cyrillic tokens (len <= 4) -- regression for 7add0b6
# ---------------------------------------------------------------------------

def test_short_cyrillic_word_does_not_match_inside_longer_word():
    """Short Cyrillic words (≤4 chars) MUST NOT match as stems inside longer words.

    Regression: 7add0b6 used only the Cyrillic-end check, removing the boundary
    from 'бас' (БАС discipline) so it matched inside 'бассейн' and 'иб' (ИБ role)
    at the start of 'ибраимов'.
    """
    # БАС (Unmanned Aerial Systems) discipline keyword
    assert _word_hit("бас система", ("бас",))            # standalone: match
    assert not _word_hit("бассейн", ("бас",))              # prefix: no match (regression)
    assert not _word_hit("обаснование", ("бас",))         # suffix: no match

    # ИБ (information security) role keyword
    assert _word_hit("иб специалист", ("иб",))         # standalone: match
    assert not _word_hit("ибраимов", ("иб",))             # prefix: no match (regression)

    # ДРОН (4 chars, exactly at the boundary)
    assert _word_hit("дрон пилот", ("дрон",))          # standalone: match
    assert not _word_hit("дрономания", ("дрон",))        # compound: no match

    # МИДЛ (4 chars)
    assert _word_hit("мидл разработчик", ("мидл",))  # standalone: match
    assert not _word_hit("полумидл", ("мидл",))          # suffix: no match


# ---------------------------------------------------------------------------
# Boundary: ASCII tokens (always require right boundary, any length)
# ---------------------------------------------------------------------------

def test_ascii_word_requires_full_word_match():
    """ASCII words must be delimited on both sides."""
    assert _word_hit("security audit", ("security",))
    assert _word_hit("backend developer", ("backend",))
    assert _word_hit("frontend engineer", ("frontend",))
    # 7add0b6 already fixed these; keep them as non-regression guards
    assert not _word_hit("backendservice", ("backend",))
    assert not _word_hit("myfrontend", ("frontend",))
    # insecurity: old code also didn't match (left boundary fails); kept for clarity
    assert not _word_hit("insecurity", ("security",))
    assert not _word_hit("cybersecurity", ("security",))


def test_short_ascii_gets_right_boundary():
    """Short abbreviations (ctf, sre, ios …) must not match mid-word."""
    assert _word_hit("ctf writeup", ("ctf",))
    assert not _word_hit("noctf", ("ctf",))
    assert _word_hit("sre team", ("sre",))
    assert not _word_hit("sremote", ("sre",))
    assert _word_hit("ios developer", ("ios",))
    assert not _word_hit("bios", ("ios",))


# ---------------------------------------------------------------------------
# Realistic query smoke-test
# ---------------------------------------------------------------------------

def test_mixed_query_no_cross_contamination():
    """All tokens detected in a realistic query; no false positives."""
    low = "сеньор бэкенд python ctf"
    assert _word_hit(low, ("senior", "сеньор", "синьор"))
    assert _word_hit(low, ("backend", "бэкенд", "бекенд"))
    assert _word_hit(low, ("ctf",))
    assert not _word_hit(low, ("security",))        # 'security' must NOT fire on 'ctf'
    assert not _word_hit("бассейн безопасности", ("бас",))  # BAS must not fire on бассейн
