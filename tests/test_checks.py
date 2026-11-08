"""Failure tests that run without an API key (pytest -q).

They test the deterministic safeguards the agents rely on: a fabricated
citation, a misquote, an invented amount and a draft that impersonates an
official position must all be caught.
"""
from agents.verify import check_citations, numbers_supported, governance_flags, quote_found
from pipeline.compare import load, align, summary
from pipeline.sections import parse_bill


def test_corpus_loaded():
    bills, secs = load()
    assert "HB-20-2322" in bills and len(secs["HB-20-2322"]) >= 10


def test_fabricated_section_is_caught():
    r = check_citations([{"claim": "x", "section": "HB-20-2322:s99", "quote": "anything"}])
    assert r[0]["check"] == "section does not exist"


def test_misquote_is_caught():
    r = check_citations([{"claim": "x", "section": "HB-20-2322:s6", "quote": "The Executive Director shall receive Salary Grade 33"}])
    assert r[0]["check"] == "quote not found in section"


def test_true_quote_passes():
    _, secs = load()
    s = secs["HB-20-2322"][0]
    words = s["text"].split()[2:14]
    r = check_citations([{"claim": "x", "section": s["id"], "quote": " ".join(words)}])
    assert r[0]["check"] == "verified"


def test_invented_amount_is_flagged():
    assert numbers_supported("Initial cost of P500 million", ["The amount necessary shall be charged to the GAA."]) == ["P500 million"]


def test_impersonation_is_flagged():
    assert governance_flags("Approved by Secretary Cruz; we recommend approval of the bill.")


def test_near_copy_detected():
    # HB 5296 closely follows HB 2322 (known duplicate in the pilot set)
    s = summary(align("HB-20-5296", "HB-20-2322"))
    assert s["same"] + s["changed"] >= 14 and s["new in A"] <= 2


def test_senate_line_numbers_removed():
    txt = "Be it enacted by the Senate\n 1            SECTION 1. Short Title. - This Act\n 2   shall be known as X.\n 3   Sec. 2. Creation. - There is created"
    p = parse_bill(txt)
    assert p["n_sections"] == 2 and p["sections"][1]["heading"] == "Creation"


def test_ocr_tolerant_quote():
    assert quote_found("There is hereby created a Department", "There is hereby crea ted a Department of Water")
