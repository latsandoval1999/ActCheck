"""Saved review state per bill: data/reviews/<bill id>.json.

Holds each agent's latest output and checks, the reviewer's approvals and edits, and a
status trail (new -> in review -> review approved -> memo drafted -> letter drafted).
On a hosted app this folder is reset when the app restarts, so every change is also copied to the owner's Google
Sheet (the same Apps Script web app as public reports, as rows with category "Workspace: review state") and read back
when the app starts. Agent outputs from live API runs and attached files are not copied (agent outputs prepared by
Claude are kept in the code repository); everything the reviewer enters is.
"""
import json
import threading
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "data" / "reviews"
STATUSES = ["new", "in review", "review approved", "memo drafted", "letter drafted"]


STATE_CATEGORY = "Workspace: review state"
NOT_SYNCED = ("research", "compaire", "apprAIsal", "review")   # large outputs of live API runs
_SYNC = {"restored": False, "timers": {}, "lock": threading.Lock()}
DELAY = 6          # seconds: quick successive changes (ticks, edits) go to the sheet as one row


def _path(bid):
    return DIR / f"{bid}.json"


def _last_time(rec):
    return max([t.get("time", "") for t in rec.get("trail") or []] + [rec.get("_synced", "")])


def _push_now(bid):
    from agents import reports
    if not reports.remote_on() or not _path(bid).exists():
        return
    rec = json.loads(_path(bid).read_text())
    slim = {k: v for k, v in rec.items() if k not in NOT_SYNCED}
    slim["trail"] = (rec.get("trail") or [])[-40:]
    body = json.dumps(slim, ensure_ascii=False)
    if len(body) > 45000:                      # a sheet cell holds 50,000 characters; the memo can be rebuilt
        body = json.dumps({k: v for k, v in slim.items() if k not in ("memo_fields", "letter_fields")}, ensure_ascii=False)
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    row = {"id": "state-" + bid + "-" + now.replace(":", "").replace("-", ""), "time": now, "bill": bid, "label": bid,
           "title": "", "category": STATE_CATEGORY, "message": body, "name": "", "email": "", "phone": "", "status": "saved"}
    try:
        reports._post({"token": reports._secret("REPORTS_TOKEN"), "report": row, "files": []})
    except Exception:
        pass


def _push(bid):
    """Copy the bill's review record to the Google Sheet a few seconds after the last change."""
    from agents import reports
    if not reports.remote_on():
        return
    with _SYNC["lock"]:
        t = _SYNC["timers"].pop(bid, None)
        if t:
            t.cancel()
        t = threading.Timer(DELAY, _push_now, args=(bid,))
        t.daemon = True
        _SYNC["timers"][bid] = t
        t.start()


def restore(force=False):
    """Once per app start: bring back review records saved in the Google Sheet (latest row per bill)."""
    if _SYNC["restored"] and not force:
        return 0
    _SYNC["restored"] = True
    from agents import reports
    if not reports.remote_on():
        return 0
    latest = {}
    for r in reports._remote_rows(force=True):
        if r.get("category") == STATE_CATEGORY and r.get("bill"):
            if str(r.get("time", "")) >= str(latest.get(r["bill"], {}).get("time", "")):
                latest[r["bill"]] = r
    n = 0
    DIR.mkdir(parents=True, exist_ok=True)
    for bid, r in latest.items():
        try:
            rec = json.loads(r.get("message") or "{}")
        except Exception:
            continue
        rec["_synced"] = str(r.get("time", ""))
        p = _path(bid)
        local = json.loads(p.read_text()) if p.exists() else None
        if local is None or _last_time(local) < rec["_synced"]:
            keep = {k: local[k] for k in NOT_SYNCED if local and k in local}
            p.write_text(json.dumps(dict(rec, **keep), indent=1, ensure_ascii=False))
            n += 1
    return n


def load(bid):
    restore()
    p = _path(bid)
    return json.loads(p.read_text()) if p.exists() else {"bill": bid, "status": "new", "trail": []}


def save(bid, key, value, note=None, trail=True):
    DIR.mkdir(parents=True, exist_ok=True)
    rec = load(bid)
    rec[key] = value
    if trail:
        rec["trail"].append({"time": datetime.now(timezone.utc).isoformat(timespec="seconds"), "event": note or f"saved {key}"})
    _path(bid).write_text(json.dumps(rec, indent=1, ensure_ascii=False))
    _push(bid)
    return rec


def set_status(bid, status, note=None):
    rec = load(bid)
    if STATUSES.index(status) > STATUSES.index(rec.get("status", "new")):
        return save(bid, "status", status, note or f"status: {status}")
    return rec


def all_status():
    restore()
    if not DIR.exists():
        return {}
    return {p.stem: json.loads(p.read_text()).get("status", "new") for p in DIR.glob("*.json")}


def queue(bid, note="Added to the review workspace"):
    """Put a bill in the review workspace (creates its record if needed)."""
    restore()
    if not _path(bid).exists():
        save(bid, "queued", datetime.now(timezone.utc).isoformat(timespec="seconds"), note)
    elif load(bid).get("removed"):
        save(bid, "removed", False, "Added back to the review workspace")
    return load(bid)


def exists(bid):
    restore()
    return _path(bid).exists()


def unqueue(bid):
    """Take a bill off the review workspace list; its saved work is kept and returns if it is added again."""
    if _path(bid).exists():
        save(bid, "removed", True, "Removed from the review workspace")


def queue_list():
    """Bills in the review workspace, most recently touched first: [(bid, record)]."""
    restore()
    if not DIR.exists():
        return []
    recs = [(p.stem, r) for p in DIR.glob("*.json") if not (r := json.loads(p.read_text())).get("removed")]
    return sorted(recs, key=lambda r: (r[1].get("trail") or [{"time": ""}])[-1]["time"], reverse=True)


def save_upload(bid, step, name, data):
    """Store a file the reviewer attached to a checklist item; returns its saved name."""
    d = DIR / "files" / bid
    d.mkdir(parents=True, exist_ok=True)
    safe = "".join(ch if ch.isalnum() or ch in "._-" else "_" for ch in name)[:80]
    (d / f"{step}_{safe}").write_bytes(data)
    return f"{step}_{safe}"


FEEDBACK_KINDS = ["Wrong or unverifiable citation", "Wrong or unsupported figure", "Missing evidence or related measure",
                  "Overstated status or certainty", "Biased or unfair wording", "Out of scope (position, politics, names)", "Other"]


def feedback(bid, step, kind, text):
    """Record a reviewer's report of a problem with an AI output (DICT-CSC JMC No. 003 s. 2026, Sec. 6(b): reporting
    and feedback mechanism). Kept in the bill's record and in logs/feedback.jsonl, which the Run log shows."""
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    item = {"time": now, "bill": bid, "step": step, "kind": kind, "text": text.strip()}
    rec = load(bid)
    save(bid, "feedback", (rec.get("feedback") or []) + [item], note=f"problem reported on {step}: {kind}")
    log = ROOT / "logs" / "feedback.jsonl"
    log.parent.mkdir(parents=True, exist_ok=True)
    with open(log, "a") as f:
        f.write(json.dumps(item, ensure_ascii=False) + "\n")
    return item
