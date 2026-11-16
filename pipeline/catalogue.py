"""One list of every bill ActCheck knows about, for the portal's Bills page.

Sources, later ones overriding earlier ones for the same bill:
  1. data/processed/bill_index.csv.gz       Open Congress Data (BetterGov.PH), House and Senate, 18th-20th Congress
  2. data/processed/senate_listing_20.csv   the Senate website's bill listing (synced by the daily check)
  3. data/watch/inbox.json                  bills found by the daily check (House PDF server, Senate listing)
  4. data/processed/bills.jsonl             bills whose full text is in the corpus (reviewable now)

Every bill gets a scope tag. The pilot scope is bills that create a national government entity;
the agents are tuned and tested on those, but every bill is listed.
"""
import csv
import gzip
import json
import re
from functools import lru_cache
from pathlib import Path

from pipeline.watch import screen, SENATE
from pipeline import typology, policy

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
HOUSE_PDF = "https://docs.congress.hrep.online/legisdocs/basic_{c}/HB{n:05d}.pdf"

SCOPE = {"entity-creating": "Creates a national agency (pilot)", "local entity (excluded)": "Local office or facility",
         "not entity-creating": "Other legislation", "no title found": "Other legislation"}
CHAMBER = {"HB": "House", "SB": "Senate"}


PROPER = {"philippines": "Philippines", "president": "President", "house of representatives": "House of Representatives",
          "senate": "Senate", "malacanang": "Malacañang", "house": "House"}


def senate_link(url):
    """Old Senate PDF links (web.senate.gov.ph/lisdata/...) now live under senate.gov.ph/legacy/lis_bills/."""
    m = re.match(r"https?://(?:web\.|legacy\.)?senate\.gov\.ph/lisdata/(.+\.pdf)$", url or "", re.I)
    return f"{SENATE}/legacy/lis_bills/{m.group(1)}" if m else url


def proper(s):
    for k, v in PROPER.items():
        s = re.sub(rf"\b{k}\b", v, s)
    return s


def _rows_index():
    p = PROC / "bill_index.csv.gz"
    if not p.exists():
        return []
    with gzip.open(p, "rt", encoding="utf-8") as f:
        return list(csv.DictReader(f))


def _rows_senate():
    out = []
    for p in sorted(PROC.glob("senate_listing_*.csv")):
        c = p.stem.rsplit("_", 1)[-1]
        with open(p, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                out.append(dict(r, chamber="SB", congress=c,
                                pdf_url=f"{SENATE}/legislative-documents/bills/{r['system_id']}" if r.get("system_id") else ""))
    return out


def _inbox():
    p = ROOT / "data" / "watch" / "inbox.json"
    return json.loads(p.read_text()) if p.exists() else []


def _enacted():
    """Bill ID -> (RA number, date approved), from the closing notes of Republic Acts (pipeline/ra_library.py)."""
    p = PROC / "ra_origin_bills.csv"
    out = {}
    if p.exists():
        with open(p, newline="", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                for b in (r.get("bills") or "").split(";"):
                    if b:
                        out[b] = (r["ra"], r.get("approved", ""))
    return out


def _nice_date(iso):
    try:
        y, m, d = (int(x) for x in iso.split("-"))
        return f"{['January','February','March','April','May','June','July','August','September','October','November','December'][m - 1]} {d}, {y}"
    except Exception:
        return ""


def fill_status(bid, congress, status, enacted, full):
    """When the source gives no status, assign one from other evidence, and say where it came from."""
    if status:
        return status, "Source listing"
    if bid in enacted:
        ra, approved = enacted[bid]
        return (f"Enacted as Republic Act No. {ra}" + (f" (approved {_nice_date(approved)})" if approved else ""),
                "Closing note of the Republic Act (Philippine Legal Documents Library, BetterGov.PH / Lawphil)")
    if str(congress) in ("18", "19"):
        if full:
            return (f"Not enacted; the {congress}th Congress has ended",
                    "Derived: not among the bills named in any Republic Act, and bills lapse when a Congress ends")
        return f"Last stage not recorded; the {congress}th Congress has ended", "Derived from the end of the Congress"
    return "Filed; later stages not in source data", "Derived: a filed bill whose later stages are not published in a source ActCheck can read"


# Detailed statuses (27 wordings across the House, Senate and Open Congress sources) mapped to four main groups, each
# with sub-headings. The Bills filter uses the main groups; each bill shows its sub-heading and the exact status.
GROUPS = {
    "PENDING": ["Filed", "First reading", "Second reading", "In the committee", "In the House of Representatives", "In the Senate",
                "In Congress (bicameral conference)", "Sent to the President"],
    "ENACTED": ["Approved by the President", "Enrolled copy sent to Malacañang", "Approved with parts vetoed", "Lapsed into law"],
    "CONSOLIDATED/SUBSTITUTED": ["In the committee report", "With an approved bill", "With a bill that lapsed into law"],
    "NOT ENACTED": ["Vetoed", "Withdrawn or archived", "Congressional session ended"],
}
GROUP_OF = {sub: g for g, subs in GROUPS.items() for sub in subs}
_RULES = [  # (pattern on the lower-case status, sub-heading), first match wins
    (r"consolidated.*lapsed into law", "With a bill that lapsed into law"),
    (r"consolidated with approved bill|consolidated with an approved", "With an approved bill"),
    (r"consolidated|substituted", "In the committee report"),
    (r"vetoed other parts|parts vetoed|line-item veto", "Approved with parts vetoed"),
    (r"^vetoed", "Vetoed"),
    (r"lapsed into law", "Lapsed into law"),
    (r"^approved by the president|^enacted as republic act", "Approved by the President"),
    (r"enrolled copy|malaca", "Enrolled copy sent to Malacañang"),
    (r"passed by both houses", "Sent to the President"),
    (r"conference|conferees", "In Congress (bicameral conference)"),
    (r"pending in the house|sent back to the house", "In the House of Representatives"),
    (r"pending in the senate|sent back to the senate", "In the Senate"),
    (r"second reading|third reading", "Second reading"),
    (r"first reading", "First reading"),
    (r"committee", "In the committee"),
    (r"withdrawn|archives|archived", "Withdrawn or archived"),
    (r"^filed", "Filed"),
]
# sub-headings that end a bill's journey; anything else in an ended Congress lapsed when that Congress adjourned
_CLOSED = set(GROUPS["ENACTED"]) | set(GROUPS["CONSOLIDATED/SUBSTITUTED"]) | {"Vetoed", "Withdrawn or archived", "Sent to the President"}


def classify(status, congress):
    """(main group, sub-heading) for a bill's status."""
    s = (status or "").lower()
    sub = next((name for rx, name in _RULES if re.search(rx, s)), None)
    if str(congress) in ("18", "19") and sub not in _CLOSED:
        sub = "Congressional session ended"
    sub = sub or "Filed"
    return GROUP_OF[sub], sub


@lru_cache(maxsize=1)
def build(_stamp=None):
    """Return a list of dicts, newest Congress and highest number first."""
    from pipeline.compare import load
    corpus, _ = load()
    bills = {}

    def put(bid, **kw):
        cur = bills.setdefault(bid, {"id": bid})
        cur.update({k: v for k, v in kw.items() if v not in (None, "")})

    for r in _rows_index():
        if not r.get("number"):
            continue
        put(r["id"], chamber=r["chamber"], congress=r["congress"], number=int(r["number"]), date_filed=r.get("date_filed"),
            title=r.get("title"), short_title=r.get("short_title"), status=r.get("status"), source_url=r.get("pdf_url"),
            source="Open Congress Data")
    for r in _rows_senate():
        put(r["id"], chamber="SB", congress=r["congress"], number=int(r["number"]), date_filed=r.get("date_filed"),
            title=r.get("title"), short_title=r.get("short_title"), status=r.get("status"), committee=r.get("committee"),
            author=r.get("author"), source_url=r.get("pdf_url"), source="Senate website")
    for x in _inbox():
        put(x["id"], chamber=x["chamber"], congress=x["congress"], number=int(x["number"]), date_filed=x.get("date_filed"),
            title=x.get("title"), short_title=x.get("short_title"), status=x.get("legislative_status"),
            source_url=x.get("pdf_url") or x.get("source_url"), found=x.get("found", "")[:10],
            source="House documents server (catch-up)" if x.get("backfill") else "Daily check",
            text_state="pending" if str(x.get("text", "")).startswith(("pending", "scanned")) else x.get("text"))
    for b in corpus.values():
        if b.get("chamber") not in CHAMBER or not b.get("congress"):
            continue
        cur = bills.get(b["id"], {})
        put(b["id"], chamber=b["chamber"], congress=str(b["congress"]), number=int(b["id"].split("-")[2]),
            title=cur.get("title") or b.get("title"), in_corpus=True)

    enacted = _enacted()
    full = len(set(r for r, _ in enacted.values())) >= 1000      # the full Republic Acts list, not a partial seed
    out = []
    for b in bills.values():
        title = b.get("title", "")
        num = b.get("number", 0)
        b["source_url"] = senate_link(b.get("source_url", ""))
        if not b.get("source_url") and b.get("chamber") == "HB" and str(b.get("congress")) == "20":
            b["source_url"] = HOUSE_PDF.format(c=20, n=num)
        cat = typology.category(title)
        app = typology.application(title, cat)
        status = " ".join((b.get("status") or "").split())
        status = proper(status[:1].upper() + status[1:].lower()) if status else ""
        status, status_basis = fill_status(b["id"], b.get("congress"), status, enacted, full)
        led = policy.ledac(f"{title} {b.get('short_title', '')}", b.get("congress"))
        text = "Full text" if b.get("in_corpus") else ("Text pending" if b.get("text_state") == "pending" else "Listing only")
        out.append({
            "id": b["id"], "label": f"{'HB' if b.get('chamber') == 'HB' else 'SB'} {num}",
            "chamber": CHAMBER.get(b.get("chamber"), b.get("chamber", "")), "congress": str(b.get("congress", "")),
            "number": num, "date_filed": b.get("date_filed", ""), "short_title": b.get("short_title", ""), "title": title,
            "status": status, "status_basis": status_basis,
            "status_group": classify(status, b.get("congress"))[0], "status_sub": classify(status, b.get("congress"))[1], "type": cat, "applies_to": app, "house_origin": typology.house_origin(cat, app),
            "bill_type": "House Bill" if b.get("chamber") == "HB" else "Senate Bill", "committee": b.get("committee", ""), "author": b.get("author", ""),
            "scope": SCOPE.get(screen(title), "Other legislation"), "text": text, "found": b.get("found", ""),
            "source": b.get("source", "Corpus"), "source_url": b.get("source_url", ""), "reviewable": bool(b.get("in_corpus")),
            "ledac": f"{led[0][0]}. {led[0][1]}" if led else "",
        })
    out.sort(key=lambda r: (-int(r["congress"] or 0), r["chamber"] != "House", -r["number"]))
    return out


def stamp():
    """Changes when any source file changes, so the portal can refresh its cached list."""
    files = [PROC / "bill_index.csv.gz", PROC / "bills.jsonl", ROOT / "data" / "watch" / "inbox.json", PROC / "ra_origin_bills.csv",
             *PROC.glob("senate_listing_*.csv")]
    return tuple(int(f.stat().st_mtime) for f in files if f.exists())
