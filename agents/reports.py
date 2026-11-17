"""Public reports: civil society and other members of the public can share inputs on a bill from the Bills page.

Storage: when the secrets REPORTS_WEBAPP_URL and REPORTS_TOKEN are set (Streamlit secrets or environment), each
report is saved to a Google Sheet in the project owner's Google Drive through a small Apps Script web app
(scripts/reports_apps_script.gs), and attachments go to a Drive folder. The app reads the sheet back, so reports
survive restarts. Without those secrets, or if the sheet cannot be reached, reports are kept on the server running
ActCheck (data/public_reports/, never committed), which resets when the hosted app restarts.

Contact details stay out of the public code and are shown only to reviewers; the public sees counts only. Handling
follows the Data Privacy Act (RA 10173): contact details are optional, used only to follow up on the report, and
collected with the sender's consent.
"""
import base64
import json
import mimetypes
import os
import re
import time
import urllib.parse
import urllib.request
import uuid
from datetime import datetime, timezone
from pathlib import Path

from agents.names import AGENT1, AGENT2, AGENT3

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "data" / "public_reports"
MAX_FILE_MB = 10
FILE_TYPES = ["pdf", "docx", "doc", "xlsx", "csv", "txt", "png", "jpg", "jpeg"]

# Report topics, grouped by the agent whose check they concern (stored as "<group>: <topic>")
OTHERS = "Others"
GROUPS = {
    AGENT1: ["Legislative history", "Earlier versions", "Counterpart bills", "Related laws"],
    AGENT2: ["Similarities or differences with related bills", "Policy design"],
    AGENT3: ["Cost and budget", "Functional overlap or duplication", "Implementation or governance risk"],
    OTHERS: ["Correction to information shown on this page", "Other concern"],
}
GROUP_HELP = {
    AGENT1: "the bill's history: earlier versions, counterpart bills and the laws it relates to",
    AGENT2: "how the bill compares with related bills, and its policy design",
    AGENT3: "cost and budget, overlap with existing agencies or programs, and implementation or governance risks",
    OTHERS: "corrections to this page, and anything else",
}
CATEGORIES = [f"{g}: {t}" for g, ts in GROUPS.items() for t in ts]
STEP = {AGENT1: 1, AGENT2: 2, AGENT3: 3, OTHERS: 0}


def category(group, topic):
    return f"{group}: {topic}"


def step_of(category):
    """Which part of the Review workspace a report concerns: 1 TrAIce, 2 CompAIre, 3 ApprAIsal, 0 the whole bill."""
    c = category or ""
    g = c.split(":")[0].strip()
    if g in STEP:
        return STEP[g]
    lc = c.lower()                      # reports filed under the earlier category names
    if "traice" in lc:
        return 1
    if "compaire" in lc:
        return 2
    if "appraisai" in lc or lc.startswith("who is affected"):
        return 3
    return 0


def valid_email(e):
    return not e or bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", e))


# ---------------------------------------------------------------- Google Sheet (Apps Script web app)
def _secret(name):
    v = os.environ.get(name, "")
    if not v:
        try:
            import streamlit as st
            v = st.secrets.get(name, "")
        except Exception:
            v = ""
    return str(v or "").strip()


def remote_on():
    return bool(_secret("REPORTS_WEBAPP_URL") and _secret("REPORTS_TOKEN"))


def sheet_status():
    """('connected' | 'error' | 'off', message) for reviewers: is the Google Sheet answering?"""
    if not remote_on():
        return "off", "Not connected: reports stay on this server until the Google Sheet is set up (README: Public reports)."
    try:
        res = _get()
    except Exception as e:
        return "error", f"The Google Sheet is set up but did not answer ({type(e).__name__}); check the web app URL in the Streamlit secrets."
    if not res.get("ok"):
        return "error", "The Google Sheet answered but refused the token; check REPORTS_TOKEN in the Streamlit secrets."
    rows = res.get("reports", [])
    pub = sum(1 for r in rows if not str(r.get("category", "")).startswith("Workspace:"))
    bills = len({r.get("bill") for r in rows if r.get("category") == "Workspace: review state"})
    return "connected", (f"Connected to the Google Sheet: {pub} public report(s) and the saved review progress of {bills} bill(s) "
                         "are stored there; they are kept after restarts.")


def storage_label():
    return "Google Sheet in the project owner's Google Drive" if remote_on() else \
        "this server only (resets when the app restarts; connect the Google Sheet to keep reports)"


_CACHE = {"t": 0.0, "rows": None}
TTL = 60


def _post(payload, timeout=60):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(_secret("REPORTS_WEBAPP_URL"), data=data,
                                 headers={"Content-Type": "application/json"}, method="POST")
    # Apps Script answers with a redirect to the result; urllib follows it with a GET
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _get(timeout=20):
    url = _secret("REPORTS_WEBAPP_URL") + "?" + urllib.parse.urlencode({"token": _secret("REPORTS_TOKEN")})
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read().decode())


def _remote_rows(force=False):
    if not remote_on():
        return []
    if not force and _CACHE["rows"] is not None and time.time() - _CACHE["t"] < TTL:
        return _CACHE["rows"]
    try:
        res = _get()
        rows = res.get("reports", []) if res.get("ok") else []
    except Exception:
        rows = _CACHE["rows"] or []
    out = []
    for r in rows:
        try:
            r["files"] = json.loads(r.get("files") or "[]")
        except Exception:
            r["files"] = []
        r["_store"] = "sheet"
        out.append(r)
    _CACHE.update(t=time.time(), rows=out)
    return out


# ---------------------------------------------------------------- save and list
QUEUE_CATEGORY = "Workspace: TrAIce queue"


def queue_for_claude(bill_id, bill_label, title):
    """Note in the same Google Sheet that a reviewer added this bill to the workspace, so the scheduled
    Claude run picks it up. Not a public report: all_reports() leaves these rows out. Runs in the background."""
    if not remote_on():
        return False
    import threading
    threading.Thread(target=save, args=(bill_id, bill_label, title, QUEUE_CATEGORY,
                                        "Added to the review workspace; queued for a TrAIce run by Claude"), daemon=True).start()
    return True


def save(bill_id, bill_label, title, category, message, name="", email="", phone="", files=()):
    rid = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:6]
    rec = {"id": rid, "time": datetime.now(timezone.utc).isoformat(timespec="seconds"), "bill": bill_id,
           "label": bill_label, "title": title, "category": category, "message": message.strip(),
           "name": name.strip(), "email": email.strip(), "phone": phone.strip(), "status": "new"}
    files = list(files or [])
    if remote_on():
        try:
            payload = {"token": _secret("REPORTS_TOKEN"), "report": rec, "files": [
                {"name": re.sub(r"[^A-Za-z0-9._ -]", "_", f.name)[-80:],
                 "type": getattr(f, "type", None) or mimetypes.guess_type(f.name)[0] or "application/octet-stream",
                 "data": base64.b64encode(f.getvalue()).decode()} for f in files]}
            res = _post(payload)
            if res.get("ok"):
                _CACHE["rows"] = None          # read the sheet again on the next look
                return dict(rec, files=res.get("files", []), _store="sheet")
        except Exception:
            pass                               # fall back to the server copy below
    DIR.mkdir(parents=True, exist_ok=True)
    folder = DIR / rid
    folder.mkdir()
    saved = []
    for f in files:
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", f.name)[-80:]
        (folder / safe).write_bytes(f.getvalue())
        saved.append(safe)
    rec["files"] = saved
    (folder / "report.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1))
    return dict(rec, _store="server")


def _local(bill_id=None):
    out = []
    for p in sorted(DIR.glob("*/report.json"), reverse=True) if DIR.exists() else []:
        try:
            r = json.loads(p.read_text())
        except Exception:
            continue
        if bill_id is None or r.get("bill") == bill_id:
            r["_dir"] = str(p.parent)
            r["_store"] = "server"
            out.append(r)
    return out


def all_reports(bill_id=None, force=False):
    """Newest first. Sheet records and any server-only copies, without duplicates."""
    remote = [r for r in _remote_rows(force) if (bill_id is None or r.get("bill") == bill_id)
              and not str(r.get("category", "")).startswith("Workspace:")]
    seen = {r.get("id") for r in remote}
    rows = remote + [r for r in _local(bill_id) if r.get("id") not in seen]
    return sorted(rows, key=lambda r: str(r.get("time", "")), reverse=True)


def file_links(r):
    """[(name, url or local path)] for a report's attachments."""
    out = []
    for f in r.get("files") or []:
        if isinstance(f, dict):
            out.append((f.get("name", "file"), f.get("url", "")))
        elif r.get("_dir"):
            out.append((f, str(Path(r["_dir"]) / f)))
    return out
