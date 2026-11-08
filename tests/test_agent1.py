"""Agent 1 tests that run without an API key."""
from agents.research import evidence_pack, entity_name
from agents.verify import check_citations
from pipeline.extract import laws_cited, substitution_list


def labels(bid):
    p = evidence_pack(bid)
    return {r["id"]: r["baseline_label"] for r in p["related"]}, p


def test_substitution_clause_parsed():
    assert substitution_list("(In substitution of Senate Bill Nos. 1199 and 1345)", "20") == ["SB-20-1199", "SB-20-1345"]


def test_law_references_parsed():
    t = "amending Republic Act No. 8435, P.D. No. 1067 and Executive Order No. 22, s. 2023"
    assert set(laws_cited(t)) == {"RA-8435", "PD-1067", "EO-22-2023"}


def test_entity_name():
    assert entity_name("AN ACT CREATING THE DEPARTMENT OF FISHERIES AND AQUATIC RESOURCES, PROVIDING") == "DEPARTMENT OF FISHERIES AND AQUATIC RESOURCES"


def test_consolidation_found():
    lab, _ = labels("SB-20-1624")
    assert lab["SB-20-1199"].startswith("consolidated") and lab["SB-20-1345"].startswith("consolidated")


def test_near_copy_found():
    lab, _ = labels("HB-20-5296")
    assert lab.get("HB-20-2322") == "refiled near-copy"


def test_earlier_congress_not_crowded_out():
    lab, _ = labels("HB-20-6789")
    assert "HB-19-9663" in lab


def test_cited_laws_reach_the_pack():
    _, p = labels("HB-20-2322")
    assert {"RA-8435", "RA-12022"} <= {l["law"] for l in p["laws"]}


def test_title_citations_checked():
    r = check_citations([{"claim": "x", "section": "law:RA-11899", "quote": "SECOND CONGRESSIONAL COMMISSION ON EDUCATION"},
                         {"claim": "x", "section": "meta:HB-19-999999", "quote": "a bill that does not exist"},
                         {"claim": "x", "section": "law:RA-8435", "quote": "creating the Department of Water Resources"}])
    assert [c["check"] for c in r] == ["verified", "section does not exist", "quote not found in section"]
