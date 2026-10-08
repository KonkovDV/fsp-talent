"""Profile discipline weight. Competition status is not an argument of the rule."""
from app.services.fsp.relevance import lcb_for_need, relevant_disciplines
from app.services.matching import CandidateFacts, NeedSpec, score


def test_map_is_the_reverse_of_the_discipline_roles():
    assert relevant_disciplines("security") == frozenset({"security"})
    assert relevant_disciplines("embedded") == frozenset({"bas", "robotics"})
    assert relevant_disciplines("ml") == frozenset({"ai", "algorithmic"})
    assert relevant_disciplines("frontend") == frozenset()
    assert relevant_disciplines(None) == frozenset()


def test_security_need_ranks_a_security_result_above_a_stronger_other_discipline():
    security = lcb_for_need("security", {"security": 0.5}, None)
    robotics = lcb_for_need("security", {"algorithmic": 0.6}, None)
    assert security[0] == 0.5 and security[1] == "profile"
    assert robotics[0] == 0.3 and robotics[1] == "other"
    need = NeedSpec(role="security", grade="middle", skills=("Python",))

    def facts(picked):
        lcb, kind, disc = picked
        return CandidateFacts(role="security", grade="middle", grade_source="assessed",
                              skills={"Python": "test_confirmed"}, test_p=0.9, test_spec="security",
                              fsp_lcb=lcb, fsp_kind=kind, fsp_discipline=disc)

    left = score(need, facts(security))
    right = score(need, facts(robotics))
    assert left.score > right.score
    assert any(r.code == "FSP_RELEVANT" and "ИБ" in r.text for r in left.reasons)
    assert any(r.code == "FSP_OTHER" for r in right.reasons)


def test_role_without_a_profile_discipline_keeps_the_best_result():
    lcb, kind, disc = lcb_for_need("frontend", {"security": 0.4, "algorithmic": 0.6}, None)
    assert (lcb, kind, disc) == (0.6, None, "algorithmic")


def test_manual_discipline_filter_uses_only_that_discipline():
    lcb, kind, disc = lcb_for_need("security", {"security": 0.5, "algorithmic": 0.9}, "security")
    assert (lcb, kind, disc) == (0.5, None, "security")
    missing, kind, disc = lcb_for_need("security", {"algorithmic": 0.9}, "security")
    assert missing == 0.0 and kind is None and disc is None


def test_profile_wins_a_tie_and_an_empty_map_is_zero():
    lcb, kind, disc = lcb_for_need("backend", {"algorithmic": 0.4, "robotics": 0.8}, None)
    assert (lcb, kind, disc) == (0.4, "profile", "algorithmic")
    assert lcb_for_need("security", {}, None) == (0.0, None, None)


def test_no_history_still_drops_the_axis():
    need = NeedSpec(role="security", grade="middle")
    result = score(need, CandidateFacts(role="security", grade="middle", grade_source="assessed", fsp_lcb=None))
    assert any(r.code == "FSP_NEUTRAL" for r in result.reasons)
    assert all(r.code not in {"FSP_RELEVANT", "FSP_OTHER"} for r in result.reasons)
