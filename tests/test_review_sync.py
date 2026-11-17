"""Review records survive an app restart: copied to the Google Sheet and restored from it."""
import json

from agents import reports, store


def test_review_state_roundtrip(tmp_path, monkeypatch):
    sheet = []
    monkeypatch.setattr(store, "DIR", tmp_path / "reviews")
    monkeypatch.setattr(store, "DELAY", 0)
    monkeypatch.setattr(reports, "remote_on", lambda: True)
    monkeypatch.setattr(reports, "_secret", lambda k: "x")
    monkeypatch.setattr(reports, "_post", lambda payload, timeout=60: sheet.append(dict(payload["report"])) or {"ok": True})
    monkeypatch.setattr(reports, "_remote_rows", lambda force=False: [dict(r) for r in sheet])
    store._SYNC["restored"] = True
    store.queue("HB-20-9897")
    store.save("HB-20-9897", "checklist", {"t1": {"0": {"done": True}}}, trail=False)
    store.save("HB-20-9897", "research", {"output": {"big": "x" * 10}}, "live run")      # not copied
    store._push_now("HB-20-9897")
    assert sheet and sheet[-1]["category"] == store.STATE_CATEGORY
    assert "research" not in json.loads(sheet[-1]["message"])
    # the app restarts: the server folder is empty
    for p in (tmp_path / "reviews").glob("*.json"):
        p.unlink()
    store._SYNC["restored"] = False
    assert store.load("HB-20-9897")["checklist"]["t1"]["0"]["done"] is True
    assert [b for b, _ in store.queue_list()] == ["HB-20-9897"]
    # review-state rows are not public reports
    monkeypatch.setattr(reports, "_local", lambda bill_id=None: [])
    assert reports.all_reports() == []
