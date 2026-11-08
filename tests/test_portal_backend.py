"""Back-end pieces the portal uses (no Streamlit, no API key)."""
from agents import store
from agents.chat import check_citations_in, workspace
from agents.report import markdown, docx_bytes


def test_store_status_only_moves_forward(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DIR", tmp_path)
    store.set_status("HB-20-1", "review approved")
    store.set_status("HB-20-1", "in review")
    assert store.load("HB-20-1")["status"] == "review approved"


def test_chat_citation_check():
    r = check_citations_in("Twelve members [HB-20-2322:s5]; see [law:RA-8435]; fake [HB-20-2322:s99]; [CR-20-AGRICOM:note]")
    assert [c["exists"] for c in r] == [True, True, False, True]


def test_workspace_has_bill_and_costing():
    w = workspace("HB-20-2322")
    assert "HB-20-2322:s5" in w and "COSTING ENGINE" in w


def test_report_exports():
    md = markdown("HB-20-2322")
    assert "ActCheck preliminary report" in md and "Fiscal implications" in md
    assert docx_bytes("HB-20-2322")[:2] == b"PK"   # a .docx is a zip file


def test_catalogue_lists_all_bills():
    from pipeline import catalogue
    rows = {r["id"]: r for r in catalogue.build(catalogue.stamp())}
    assert len(rows) > 30000                                   # every bill, not only the pilot scope
    assert rows["HB-20-2322"]["reviewable"] and rows["HB-20-2322"]["scope"] == catalogue.SCOPE["entity-creating"]
    assert {r["chamber"] for r in rows.values()} == {"House", "Senate"}
    assert any(r["scope"] == "Other legislation" for r in rows.values())
