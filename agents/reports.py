"""Public reports: civil society and other members of the public can share inputs on a bill from the Bills page.

Kept on the server running ActCheck (data/public_reports/, never committed to the repository), so contact details
stay out of the public code. Reviewers see them; the public sees only counts. On the hosted prototype the folder
resets when the app restarts. Handling follows the Data Privacy Act (RA 10173): contact details are optional, used
only to follow up on the report, and collected with the sender's consent.
"""
import json
import re
import uuid
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIR = ROOT / "data" / "public_reports"
MAX_FILE_MB = 10
FILE_TYPES = ["pdf", "docx", "doc", "xlsx", "csv", "txt", "png", "jpg", "jpeg"]

# Categories follow what each agent checks
CATEGORIES = [
    "Legislative history (TrAIce): earlier versions, counterpart bills, related laws",
    "Changes and design (CompAIre): how it differs from related bills, design options",
    "Cost and budget impact (AppraisAI): cost, source of funds, fiscal risk",
    "Overlap with existing agencies, programs or laws (AppraisAI)",
    "Implementation, governance and risks (AppraisAI)",
    "Who is affected: communities, sectors, equity",
    "Correction to information shown on this page",
    "Other",
]


def valid_email(e):
    return not e or bool(re.match(r"^[^@\s]+@[^@\s]+\.[^@\s]+$", e))


def save(bill_id, bill_label, title, category, message, name="", email="", phone="", files=()):
    DIR.mkdir(parents=True, exist_ok=True)
    rid = datetime.now(timezone.utc).strftime("%Y%m%d%H%M%S") + "-" + uuid.uuid4().hex[:6]
    folder = DIR / rid
    folder.mkdir()
    saved = []
    for f in files or []:
        safe = re.sub(r"[^A-Za-z0-9._-]", "_", f.name)[-80:]
        (folder / safe).write_bytes(f.getvalue())
        saved.append(safe)
    rec = {"id": rid, "time": datetime.now(timezone.utc).isoformat(timespec="seconds"), "bill": bill_id, "label": bill_label,
           "title": title, "category": category, "message": message.strip(), "name": name.strip(), "email": email.strip(),
           "phone": phone.strip(), "files": saved}
    (folder / "report.json").write_text(json.dumps(rec, ensure_ascii=False, indent=1))
    return rec


def all_reports(bill_id=None):
    out = []
    for p in sorted(DIR.glob("*/report.json"), reverse=True) if DIR.exists() else []:
        try:
            r = json.loads(p.read_text())
        except Exception:
            continue
        if bill_id is None or r.get("bill") == bill_id:
            r["_dir"] = str(p.parent)
            out.append(r)
    return out
