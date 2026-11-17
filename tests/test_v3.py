"""Tests for the bill typology, DBM-format documents, BILLy search and the review queue (no API key)."""
import io

from pipeline import typology as T
from agents import documents as D, billy, store


def test_typology_examples_from_coding_frame():
    cases = {
        "AN ACT CREATING THE DEPARTMENT OF MIGRANT WORKERS, DEFINING ITS POWERS AND FUNCTIONS": "Government organization and mandates",
        "AN ACT GRANTING PHILIPPINE CITIZENSHIP TO JUSTIN DONTA BROWNLEE": "Legislative franchises and individual grants",
        "AN ACT CONVERTING THE MUNICIPALITY OF BALIWAG IN THE PROVINCE OF BULACAN INTO A COMPONENT CITY": "Territorial organization and charters",
        "AN ACT DECLARING SEPTEMBER 8 OF EVERY YEAR A SPECIAL NONWORKING HOLIDAY IN THE CITY OF MARIKINA": "Commemorations, holidays and naming",
        "AN ACT INCREASING THE BED CAPACITY OF THE PHILIPPINE GENERAL HOSPITAL": "Public facilities and infrastructure",
        "AN ACT AMENDING THE NATIONAL INTERNAL REVENUE CODE TO REDUCE THE INCOME TAX": "Taxation and revenue",
        "AN ACT PENALIZING FINANCIAL ACCOUNT SCAMMING": "Offenses and penalties",
    }
    for title, want in cases.items():
        assert T.category(title) == want, title
    assert T.application("AN ACT GRANTING PHILIPPINE CITIZENSHIP TO JUSTIN DONTA BROWNLEE") == "Private or named grantee"
    assert T.application("AN ACT DECLARING A HOLIDAY IN THE CITY OF MARIKINA") == "Local application"
    assert T.house_origin("Taxation and revenue", "General or public") and not T.house_origin("Regulation and standards", "General or public")


def test_memo_prefill_keeps_recommendation_with_reviewer():
    f = D.memo_prefill("HB-20-2322", {"salient": "HB No. 2322 seeks ...", "comments": "On the scope\n4.1 Section 4 ...",
                                      "fiscal": "5.1 ...", "recommendation": "7.1 This Department interposes no objection ..."},
                       referrals=[{"bureau": "OPCCB", "name": "Organization, Position Classification and Compensation Bureau", "why": "New positions"}])
    assert f["memo_for"] == "THE SECRETARY" and "HOUSE BILL NO. 2322" in f["subject"] and "(OPCCB)" in f["s1"]
    assert not D.position_decided(f)                                        # ApprAIsal only proposes Part VII
    ai = D.apply_ai(f, {"s2": "Section 4 provides that ...", "s7": "We recommend SUPPORT."})
    assert ai["s2"].startswith("Section 4") and not D.position_decided(ai)   # an agent cannot set it
    decided = D.set_recommendation(f, "7.1 This Department interposes no objection to the proposed measure as filed.")
    assert D.position_decided(decided)


def test_word_documents_use_tahoma_and_parts():
    from docx import Document
    f = D.memo_prefill("HB-20-2322", {"salient": "x"})
    doc = Document(io.BytesIO(D.memo_docx(f)))
    text = "\n".join(p.text for p in doc.paragraphs)
    assert "DEPARTMENT OF BUDGET AND MANAGEMENT" in text and D.SIGNATURE in text and "II. Salient Features" in text
    assert "VI. Possible Duplication" not in text                           # Part VI only when a duplication was found
    assert doc.styles["Normal"].font.name == "Tahoma"
    lf = D.letter_prefill("SB-20-1624", D.set_recommendation(f, "7.1 This Department interposes no objection to the proposed measure as filed."))
    ldoc = Document(io.BytesIO(D.letter_docx(lf)))
    assert "Senate of the Philippines" in "\n".join(p.text for p in ldoc.paragraphs) and "interposes no objection" in lf["p2"]


def test_billy_search_mode_cites_sections():
    hits = billy.search("HB-20-2322", "How is it funded?")
    assert hits and hits[0][0] == "HB-20-2322:s13"
    ans, mode = billy.answer("HB-20-2322", [], "How is it funded?", live=False)
    assert mode == "search" and "[HB-20-2322:s13]" in ans


def test_review_queue(tmp_path, monkeypatch):
    monkeypatch.setattr(store, "DIR", tmp_path)
    store.queue("HB-20-2322")
    store.queue("SB-20-1624")
    assert {k for k, _ in store.queue_list()} == {"HB-20-2322", "SB-20-1624"}
    name = store.save_upload("HB-20-2322", "s1-0", "note file.pdf", b"x")
    assert (tmp_path / "files" / "HB-20-2322" / name).exists()
