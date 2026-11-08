"""Saved review state per bill: data/reviews/<bill id>.json.

Holds each agent's latest output and checks, the reviewer's approvals and edits, and a
status trail (new -> in review -> review approved -> memo drafted -> letter drafted).
On a hosted app this folder is reset when the app restarts; download reports to keep them.
"""
import json
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "data" / "reviews"
STATUSES = ["new", "in review", "review approved", "memo drafted", "letter drafted"]


def _path(bid):
    return DIR / f"{bid}.json"


def load(bid):
    p = _path(bid)
    return json.loads(p.read_text()) if p.exists() else {"bill": bid, "status": "new", "trail": []}


def save(bid, key, value, note=None, trail=True):
    DIR.mkdir(parents=True, exist_ok=True)
    rec = load(bid)
    rec[key] = value
    if trail:
        rec["trail"].append({"time": datetime.now(timezone.utc).isoformat(timespec="seconds"), "event": note or f"saved {key}"})
    _path(bid).write_text(json.dumps(rec, indent=1, ensure_ascii=False))
    return rec


def set_status(bid, status, note=None):
    rec = load(bid)
    if STATUSES.index(status) > STATUSES.index(rec.get("status", "new")):
        return save(bid, "status", status, note or f"status: {status}")
    return rec


def all_status():
    if not DIR.exists():
        return {}
    return {p.stem: json.loads(p.read_text()).get("status", "new") for p in DIR.glob("*.json")}


def queue(bid, note="Added to the review workspace"):
    """Put a bill in the review workspace (creates its record if needed)."""
    if not _path(bid).exists():
        save(bid, "queued", datetime.now(timezone.utc).isoformat(timespec="seconds"), note)
    return load(bid)


def queue_list():
    """Bills in the review workspace, most recently touched first: [(bid, record)]."""
    if not DIR.exists():
        return []
    recs = [(p.stem, json.loads(p.read_text())) for p in DIR.glob("*.json")]
    return sorted(recs, key=lambda r: (r[1].get("trail") or [{"time": ""}])[-1]["time"], reverse=True)


def save_upload(bid, step, name, data):
    """Store a file the reviewer attached to a checklist item; returns its saved name."""
    d = DIR / "files" / bid
    d.mkdir(parents=True, exist_ok=True)
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in name)[:80]
    (d / f"{step}_{safe}").write_bytes(data)
    return f"{step}_{safe}"
