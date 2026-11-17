"""ApprAIsal version 3: PS/MOOE/CO estimate, fiscal table, duplication under RA 12231, recommendation options."""
from agents import appraise, budget, compaire, costing, traice


def test_budget_estimate_close_to_dbm_reference():
    e = budget.estimate(358, "department")                  # the DBM reference central office (358 positions)
    assert 130e6 < e["mooe"] < 160e6 and 80e6 < e["co"] < 110e6
    assert e["total"] == e["ps"] + e["mooe"] + e["co"]


def _ctx():
    t = traice.saved_ai("HB-20-2322")["output"]
    t = traice.normalize(t, "HB-20-2322", {"fiscal_requirements": t.get("fiscal_requirements")})
    c = compaire.normalize(compaire.saved_ai("HB-20-2322")["output"], "HB-20-2322", {})
    return t, c


def test_rule_draft_parts_and_options():
    t, c = _ctx()
    a = appraise.rule_draft("HB-20-2322", t, c, costing.cost_range("HB-20-2322"))
    assert a["recommendation"]["option"] in appraise.OPTIONS
    assert a["memo"]["V"][0].startswith("5.1 ") and a["memo"]["VII"][0].startswith("7.1 This Department")
    assert a["duplications"] and not a["intent_to_abolish"] and "RA No. 12231" in a["memo"]["VI"][0]
    assert {"OPCCB", "BTB", "SPIB"} <= {r["bureau"] for r in a["referrals"]}
    assert all(r["bureau"] in appraise.BUREAUS for r in a["referrals"])


def test_invented_peso_figure_is_flagged():
    t, c = _ctx()
    a = appraise.rule_draft("HB-20-2322", t, c, costing.cost_range("HB-20-2322"))
    bad = dict(a, memo={"V": ["5.1 The Commission would need P999.9 million."]})
    assert any("figure not produced" in x["check"] for x in appraise.check_output(bad, a))
    assert all(x["check"] == "verified" for x in appraise.check_output(a, a))


def test_harmonize_drops_repeated_sentences():
    s = "The Commission's functions overlap with the oversight committee under RA No. 8435 and should be delineated clearly."
    out = appraise.harmonize("4.1 " + s, "6.1 " + s + " A new point that is long enough to be kept in the second part of the memo.")
    assert s in out[0] and s not in out[1] and "A new point" in out[1]


def test_bureau_coverage_matches_funding_agency():
    from agents import appraise
    g = appraise.coverage("HB-20-2322")
    assert g[0]["bureau"] == "BMB-C" and g[0]["role"] == "funding"
    assert any("Congress" in a for a in g[0]["agencies"])
    # a BMB whose coverage has no agency named in the bill is flagged
    out = {"target": "HB-20-2322", "recommendation": {"option": "a"}, "referrals": [{"bureau": "BMB-B"}], "fiscal_rows": [], "memo": {}}
    draft = {"estimate": {"low": {k: 1 for k in ("ps", "mooe", "co", "total", "recurring")},
                          "high": {k: 1 for k in ("ps", "mooe", "co", "total", "recurring")}}}
    checks = appraise.check_output(out, draft)
    assert any(c["check"].startswith("no agency named") for c in checks)
