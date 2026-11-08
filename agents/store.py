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


def save(bid, key, value, note=None):
    DIR.mkdir(parents=True, exist_ok=True)
    rec = load(bid)
    rec[key] = value
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
