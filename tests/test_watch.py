"""Watcher tests with fake sources (no network)."""
import json

import pipeline.watch as w


def test_screen_rules():
    assert w.screen("AN ACT CREATING THE DEPARTMENT OF WATER RESOURCES, DEFINING ITS POWERS") == "entity-creating"
    assert w.screen("AN ACT ESTABLISHING A GENERAL HOSPITAL IN THE CITY OF ILOILO") == "local entity (excluded)"
    assert w.screen("AN ACT INCREASING THE PENALTIES FOR SMUGGLING") == "not entity-creating"


def test_title_extraction():
    t = "HOUSE BILL NO. 1\n\nAN ACT CREATING THE PHILIPPINE SPACE AUTHORITY,\nAND FOR OTHER PURPOSES\n\nEXPLANATORY NOTE\n..."
    assert w.title_of(t).startswith("AN ACT CREATING THE PHILIPPINE SPACE AUTHORITY")


def test_run_with_fake_sources(tmp_path, monkeypatch):
    monkeypatch.setattr(w, "WATCH", tmp_path)
    monkeypatch.setattr(w, "STATE", tmp_path / "state.json")
    monkeypatch.setattr(w, "INBOX", tmp_path / "inbox.json")
    monkeypatch.setattr(w, "TEXT", tmp_path / "text")
    (tmp_path / "state.json").write_text(json.dumps({"congress": "20", "last_seen": {"HB": 100, "SB": 50}, "pending": {}, "runs": []}))
    pages = {101: "AN ACT CREATING THE NATIONAL SPACE COMMISSION, APPROPRIATING FUNDS\n\nEXPLANATORY NOTE",
             102: "AN ACT AMENDING THE TARIFF CODE\n\nEXPLANATORY NOTE"}
    monkeypatch.setattr(w, "SOURCES", {"HB": lambda n: (b"%PDF fake", "url") if n in pages else (None, "HTTP 404"),
                                      "SB": lambda n: (None, "unavailable (URLError)")})
    monkeypatch.setattr(w, "pdf_to_text", lambda data: (pages[101] if b"fake" in data and not hasattr(w, "_n") else "", "pdf_text"))
    seq = iter([pages[101], pages[102]])
    monkeypatch.setattr(w, "pdf_to_text", lambda data: (next(seq), "pdf_text"))
    rep = w.run(max_probe=5, stop_after=3, delay=0)
    inbox = json.loads((tmp_path / "inbox.json").read_text())
    assert [x["id"] for x in inbox] == ["HB-20-101", "HB-20-102"]
    assert inbox[0]["status"] == "new" and inbox[1]["status"] == "not for review"
    assert "SB" in rep["errors"]                      # Senate down -> reported, not "no bills"
    st = json.loads((tmp_path / "state.json").read_text())
    assert st["last_seen"]["HB"] == 102 and "103" in st["pending"]["HB"]
