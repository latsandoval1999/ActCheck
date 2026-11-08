"""Watcher tests with fake sources (no network)."""
import json

from datetime import date

import pipeline.watch as w

DATE1 = date.today().strftime("%B %d, %Y")


def test_screen_rules():
    assert w.screen("AN ACT CREATING THE DEPARTMENT OF WATER RESOURCES, DEFINING ITS POWERS") == "entity-creating"
    assert w.screen("AN ACT ESTABLISHING A GENERAL HOSPITAL IN THE CITY OF ILOILO") == "local entity (excluded)"
    assert w.screen("AN ACT INCREASING THE PENALTIES FOR SMUGGLING") == "not entity-creating"


def test_title_extraction():
    t = "HOUSE BILL NO. 1\n\nAN ACT CREATING THE PHILIPPINE SPACE AUTHORITY,\nAND FOR OTHER PURPOSES\n\nEXPLANATORY NOTE\n..."
    assert w.title_of(t).startswith("AN ACT CREATING THE PHILIPPINE SPACE AUTHORITY")


def _setup(tmp_path, monkeypatch, last_sb=50):
    monkeypatch.setattr(w, "WATCH", tmp_path)
    monkeypatch.setattr(w, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(w, "INBOX", tmp_path / "inbox.json")
    monkeypatch.setattr(w, "TEXT", tmp_path / "text")
    monkeypatch.setattr(w, "SENATE_LISTING", tmp_path / "senate_listing.csv")
    (tmp_path / "state.json").write_text(json.dumps({"congress": "20", "last_seen": {"HB": 100, "SB": last_sb}, "pending": {}, "runs": []}))


def test_run_with_fake_sources(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    pages = {101: "AN ACT CREATING THE NATIONAL SPACE COMMISSION, APPROPRIATING FUNDS\n\nEXPLANATORY NOTE",
             102: "AN ACT AMENDING THE TARIFF CODE\n\nEXPLANATORY NOTE"}
    monkeypatch.setattr(w, "SOURCES", {"HB": lambda n: (b"%PDF fake", "url") if n in pages else (None, "HTTP 404")})
    monkeypatch.setattr(w, "senate_list_page", lambda p: (_ for _ in ()).throw(OSError("site down")))
    seq = iter([pages[101], pages[102]])
    monkeypatch.setattr(w, "pdf_to_text", lambda data: (next(seq), "pdf_text"))
    rep = w.run(max_probe=5, stop_after=3, delay=0)
    inbox = json.loads((tmp_path / "inbox.json").read_text())
    assert [x["id"] for x in inbox] == ["HB-20-101", "HB-20-102"]
    assert all(x["status"] == "new" for x in inbox)                 # every bill is listed
    assert inbox[0]["screen"] == "entity-creating" and inbox[1]["screen"] == "not entity-creating"
    assert "SB" in rep["errors"]                      # Senate down -> reported, not "no bills"
    st = json.loads((tmp_path / "state.json").read_text())
    assert st["last_seen"]["HB"] == 102 and "103" in st["pending"]["HB"]


def test_senate_listing_and_texts(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(w, "SOURCES", {"HB": lambda n: (None, "HTTP 404")})
    raw = [{"id": "9001", "no": "SBN-52", "title": "TARIFF ACT", "longTitle": "AN ACT AMENDING THE TARIFF CODE",
            "dateFiled": DATE1, "legislativeStatus": "PENDING FIRST READING", "subjects": ["TARIFF"]},
           {"id": "9000", "no": "SBN-51", "title": "SPACE AGENCY ACT",
            "longTitle": "AN AC&#1058; CREATING THE PHILIPPINE SPACE AUTHORITY", "dateFiled": "January 05, 2020"},
           {"id": "8000", "no": "SBN-40", "title": "OLD BILL", "longTitle": "AN ACT ON SOMETHING OLD"},
           {"id": "8500", "no": "SBN-45", "title": "OLDER NEW", "longTitle": "AN ACT AMENDING SOMETHING", "dateFiled": "January 05, 2020"}]
    monkeypatch.setattr(w, "senate_list_page", lambda p: ([w.senate_row(d) for d in raw], False))
    got = []
    monkeypatch.setattr(w, "senate_pdf", lambda sid: (got.append(sid), (b"%PDF x", "pdf-url"))[1])
    monkeypatch.setattr(w, "pdf_to_text", lambda data: ("AN ACT ...\n\nEXPLANATORY NOTE", "pdf_text"))
    rep = w.run(max_probe=2, stop_after=1, delay=0, max_pdfs=1)
    inbox = {x["id"]: x for x in json.loads((tmp_path / "inbox.json").read_text())}
    assert set(inbox) == {"SB-20-51", "SB-20-52"}   # SBN-40: before the last seen bill; SBN-45: old and outside the pilot scope
    assert inbox["SB-20-51"]["title"] == "AN ACT CREATING THE PHILIPPINE SPACE AUTHORITY"   # entity + look-alike letter cleaned
    assert got == ["9000"] and inbox["SB-20-51"]["text"] == "saved"   # pilot-scope bill fetched first
    assert inbox["SB-20-52"]["text"] == "pending"                     # the rest waits for later runs
    assert inbox["SB-20-52"]["date_filed"] == w.iso_date(DATE1)
    assert (tmp_path / "senate_listing.csv").read_text().count("\n") == 5   # header + 4 bills, all listed
    assert rep["senate_texts"] == {"fetched": 1, "still_pending": 1}


def test_house_catch_up(tmp_path, monkeypatch):
    _setup(tmp_path, monkeypatch)
    monkeypatch.setattr(w, "known_house_numbers", lambda: {100, 98, 97})
    pages = {99: "AN ACT CREATING THE PHILIPPINE SPACE AUTHORITY\n\nEXPLANATORY NOTE", 95: "AN ACT AMENDING THE TARIFF CODE\n\nEXPLANATORY NOTE"}
    calls = []
    monkeypatch.setattr(w, "SOURCES", {"HB": lambda n: (calls.append(n), (b"%PDF", f"url{n}") if n in pages else (None, "HTTP 404"))[1]})
    monkeypatch.setattr(w, "pdf_to_text", lambda data, ocr=True: (pages[calls[-1]], "pdf_text"))
    monkeypatch.setattr(w, "senate_list_page", lambda p: ([], False))
    rep = w.run(max_probe=1, stop_after=1, delay=0, backfill=3)
    inbox = {x["id"]: x for x in json.loads((tmp_path / "inbox.json").read_text())}
    assert {"HB-20-99", "HB-20-95"} <= set(inbox) and inbox["HB-20-99"]["backfill"]
    assert rep["found"] == [] or all(not f["id"].startswith("HB-20-9") for f in rep["found"])   # catch-up is not 'new'
    st = json.loads((tmp_path / "state.json").read_text())
    assert 96 in st["backfill"]["absent"] and st["runs"][-1]["catch_up_added"] == 2
