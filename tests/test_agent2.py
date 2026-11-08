"""Agent 2 tests that run without an API key."""
from agents.diagnosis import fact_diff, family_designs, build_messages, check_output


def test_fact_diff_catches_composition_and_funding():
    d = fact_diff("SB-20-1624", "SB-20-1199")
    assert d["members"]["differs"] and d["peso_amounts"]["differs"]


def test_near_copy_has_no_fact_differences_in_key_fields():
    d = fact_diff("HB-20-5296", "HB-20-2322")
    assert not d["members"]["differs"] and not d["head_salary_grades"]["differs"]


def test_family_designs_listed():
    assert any("WATER" in x["design"] for x in family_designs("HB-20-6789"))


def test_prompt_omits_identical_sections_text():
    _, user, rows = build_messages("HB-20-5296", "HB-20-2322")
    assert "SECTIONS THE BASELINE FOUND IDENTICAL" in user and len(user) < 60000


def test_checks_flag_bad_labels_and_fake_quotes():
    out = {"differences": [{"category": "vibes", "fiscal_direction": "huge", "description": "x",
                            "target_section": "SB-20-1624:s13", "target_quote": "One billion pesos",
                            "reference_section": "SB-20-1199:s99", "reference_quote": "x"}]}
    ch = check_output(out, "SB-20-1624", "SB-20-1199")
    assert {c["check"] for c in ch["citations"]} == {"quote not found in section", "section does not exist"}
    assert any("category" in f for f in ch["flags"]) and any("fiscal direction" in f for f in ch["flags"])


def test_true_quote_verified():
    out = {"differences": [{"category": "funding", "fiscal_direction": "likely raises cost", "description": "x",
                            "target_section": "SB-20-1624:s13", "target_quote": "The amount of Two hundred million pesos (P200,000,000) for the initial implementation of this Act",
                            "reference_section": "", "reference_quote": ""}]}
    assert check_output(out, "SB-20-1624", "SB-20-1199")["citations"][0]["check"] == "verified"
