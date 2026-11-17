"""CompAIre version 3: rule draft, Claude's saved run, checks and grade."""
from agents import compaire, traice


def test_rule_draft_structure():
    t = traice.saved_ai("HB-20-2322")["output"]
    d = compaire.rule_draft("HB-20-2322", t)
    assert d["source"] == "rules" and d["rows"]
    assert all(r["recommendation"] in compaire.RECS for r in d["rows"])
    assert "SB-20-1624" in d["comparators"] and not any(c.startswith("CR-") for c in d["comparators"])
    assert compaire.grade("HB-20-2322", d)["points"] <= 6           # rule drafts are capped at B


def test_saved_run_verified_and_memo_only_decisions():
    sv = compaire.saved_ai("HB-20-2322")
    checks = compaire.check_output(sv["output"])
    assert checks and all(c["check"] == "verified" for c in checks)
    text = compaire.memo_text(sv["output"])
    assert text.startswith("On the") and "4.1 " in text
    retained = [r["section_ref"].split(" (")[0] for r in sv["output"]["rows"] if r["recommendation"] == "Retain provision"]
    assert all(f"{x} of HB No. 2322" not in text for x in retained)


def test_bad_recommendation_is_flagged():
    out = {"target": "HB-20-2322", "rows": [{"section_ref": "Section 5", "target_section": "", "recommendation": "Keep it"}]}
    assert any("unknown recommendation" in c["check"] for c in compaire.check_output(out))


def test_self_critique_points_and_flattering_flag():
    from agents import compaire
    rows = [{"area": a, "why": "A defined scope ties the work to measurable results."} for a in ("Scope", "Funding", "Composition")]
    honest = {"rows": rows, "self_critique": [
        {"area": "Scope", "objection": "A fixed list may leave out issues that arise later in the term.", "verdict": "weakened", "condition": "The list is a minimum."},
        {"area": "Funding", "objection": "An amount in law may be outdated by enactment.", "verdict": "stands", "condition": ""},
        {"area": "Composition", "objection": "Secretaries as members may weaken independence.", "verdict": "weakened", "condition": "They do not vote."}],
        "theory_of_change": {"problem": "p", "mechanism": "m", "outcome": "o", "weakest_assumption": "w"}}
    pts = compaire.critique_points(honest)
    assert pts[0].startswith("Theory of change") and not compaire.flattering(honest)
    flat = dict(honest, self_critique=[{"area": r["area"], "objection": "A defined scope ties the work to measurable results.",
                                        "verdict": "stands", "condition": ""} for r in rows])
    reasons = compaire.flattering(flat)
    assert any("every objection" in r for r in reasons) and any("repeats" in r for r in reasons)
    assert any("Possible flattering critique" in p for p in compaire.critique_points(flat))
    bad = dict(honest, self_critique=[{"area": "Scope", "objection": "x", "verdict": "fine"}])
    assert any("self-critique" in c["check"] for c in compaire.check_output(dict(bad, target="HB-20-2322")))
