"""TrAIce version 3: the rule-based draft (no AI)."""
from agents import research, traice
from pipeline import policy
from pipeline.compare import load


def _draft(bid):
    b = load()[0][bid]
    return traice.rule_draft(bid, research.evidence_pack(bid), {"date_filed": "July 28, 2025"},
                             policy.context({"title": b["title"], "congress": b["congress"]}), "Government organization and mandates")


def test_hb2322_draft():
    d = _draft("HB-20-2322")
    assert d["proposal"].startswith("HB No. 2322 proposes to establish a three-year Congressional Commission on Agriculture and Fisheries (AGRICOM)")
    assert "Government Optimization Act (RA No. 12231)" in d["alignment"] and "Food Security" in d["alignment"]
    assert "Sections 114\u2013116 of RA No. 8435" in d["related_measures_policy"]
    assert "Section 13 (Appropriations)" in d["salient_features"]
    labs = {r["relationship"] for r in d["related"]}
    assert labs <= set(traice.LABELS) and traice.LABELS[3] in labs
    assert any(f["item"] == "Initial funding" for f in d["fiscal_requirements"])
    assert not any(traice.PACK_WORDS.search(c) for c in d["reviewer_checks"])


def test_normalize_maps_old_labels():
    d = _draft("HB-20-2322")
    out = traice.normalize({"related": [{"id": "SB-20-1199", "relationship": "counterpart in other chamber"}],
                            "gaps": ["Not in the evidence pack", "Check the committee report"]}, "HB-20-2322", d)
    assert out["related"][0]["relationship"] == "Senate version"
    assert "Check the committee report" in out["reviewer_checks"] and not any("pack" in c for c in out["reviewer_checks"])


def test_altered_figure_in_quote_is_caught():
    """Red-team case (17 Nov 2026): a quote with a changed amount used to pass the fuzzy match."""
    from agents.verify import quote_found
    from pipeline.compare import load
    t = next(x for x in load()[1]["RA-8435"] if x["no"] == 116)["text"]
    assert quote_found("an initial amount of Twenty million pesos (P20,000,000.00) is hereby appropriated", t)
    assert not quote_found("an initial amount of Fifty million pesos (P50,000,000.00) is hereby appropriated", t)


def test_grade_rules_capped_and_claude_strong():
    d = _draft("HB-20-2322")
    g = traice.grade("HB-20-2322", d)
    assert g["grade"] in ("B", "C", "D") and g["points"] <= 6
    sv = traice.saved_ai("HB-20-2322")
    g2 = traice.grade("HB-20-2322", traice.normalize(sv["output"], "HB-20-2322", d), sv["checks"])
    assert g2["grade"] == "A"
