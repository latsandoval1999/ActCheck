"""Daily watcher (TrAIce's monitoring step): find newly filed House and Senate bills, read them,
tag the ones in the pilot scope (bills that create a national government entity) and list ALL of
them in the portal.

How it finds new bills (politely, without bypassing any site protection):
  * House: checks the House legislative-documents PDF server for the next bill numbers after
    the highest one already seen (docs.congress.hrep.online/legisdocs/basic_20/HB#####.pdf).
    The congress.gov.ph listing pages use a bot challenge, so they are not scraped.
  * Senate: reads the public bill listing behind senate.gov.ph/legislative-documents/bills
    (/lis/documents_v2, allowed by robots.txt), saves every Senate bill's metadata to
    data/processed/senate_listing_20.csv, then follows each new bill's detail record to its PDF
    (/legacy/lis_bills/...). A failure is reported as "source unavailable", never as "no new bills".

Each run:
  1. House: probes up to --max-probe numbers; stops after --stop-after consecutive misses;
     missing numbers are re-checked on later runs for --pending-days days (PDFs are often late)
  2. Senate: syncs the listing, adds new bills, downloads up to --max-pdfs bill texts per run
     (pilot-scope bills first; the rest are fetched on later runs)
  3. screens each title (pilot scope = creates a national government entity)
  4. saves text (pdftotext, OCR with tesseract if the PDF is scanned) under data/raw_text/_watch/
  5. records every bill in data/watch/inbox.json (text: saved / pending)
  6. optional --triage: runs TrAIce on new pilot-scope bills if ANTHROPIC_API_KEY is set

    python -m pipeline.watch                 # one run (then: python -m pipeline.build_corpus)
    python -m pipeline.watch --dry-run       # list what would be checked
"""
import argparse
import csv
import html
import json
import re
import shutil
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone, timedelta
from pathlib import Path

from pipeline.fetch_bills import allowed, USER_AGENT

ROOT = Path(__file__).resolve().parents[1]
WATCH = ROOT / "data" / "watch"
TEXT = ROOT / "data" / "raw_text" / "_watch"
STATE = WATCH / "state.json"
INBOX = WATCH / "inbox.json"
CONGRESS = "20"

HOUSE_PDF = "https://docs.congress.hrep.online/legisdocs/basic_{c}/HB{n:05d}.pdf"
SENATE = "https://senate.gov.ph"
SENATE_LIST = SENATE + "/lis/documents_v2?document_type=bills&congress={c}th+Congress&type=SBN&sort_by=no&sort_order=desc&page={p}&per_page=100"
SENATE_DETAIL = SENATE + "/lis/bills/{sid}/comprehensive"
SENATE_PDF = SENATE + "/legacy/lis_bills/{path}"
SENATE_LISTING = ROOT / "data" / "processed" / f"senate_listing_{CONGRESS}.csv"
LISTING_FIELDS = ["id", "number", "system_id", "date_filed", "short_title", "title", "author", "status", "status_date",
                  "committee", "subjects"]
PILOT = "entity-creating"
ENTITY_RX = re.compile(
    r"(CREATING|ESTABLISHING|CREATION OF|ESTABLISHMENT OF|CONSTITUTING)\b[^.;]{0,140}?\b"
    r"(DEPARTMENT|AUTHORITY|COMMISSION|BUREAU|OFFICE|COUNCIL|AGENCY|BOARD|INSTITUTE|CORPORATION|ADMINISTRATION|CENTER)\b", re.I)
LOCAL_RX = re.compile(r"HOSPITAL|SCHOOL|COLLEGE|UNIVERSITY|CAMPUS|BARANGAY|DISTRICT OFFICE|DISTRICT ENGINEERING|"
                      r"EXTENSION OFFICE|FIELD OFFICE|SATELLITE|BRANCH|REGIONAL TRIAL COURT|MUNICIPAL TRIAL|CITY OF|MUNICIPALITY OF", re.I)


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def load_json(p, default):
    return json.loads(p.read_text()) if p.exists() else default


def initial_state():
    """Start from the highest bill numbers already in the corpus."""
    from pipeline.compare import load
    bills, _ = load()
    hi = {"HB": 0, "SB": 0}
    for b in bills.values():
        if b["chamber"] in hi and b["congress"] == CONGRESS:
            hi[b["chamber"]] = max(hi[b["chamber"]], int(b["id"].split("-")[2]))
    return {"congress": CONGRESS, "last_seen": hi, "pending": {}, "runs": []}


def http_get(url, timeout=60, accept=None):
    headers = {"User-Agent": USER_AGENT}
    if accept:
        headers["Accept"] = accept
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def clean(s):
    """Unescape HTML codes and replace Cyrillic look-alike letters found in Senate titles."""
    s = html.unescape(s or "")
    s = s.translate(str.maketrans("АВСЕНІКМОРТХаеорсх", "ABCEHIKMOPTXaeopcx"))
    return " ".join(s.split())


def iso_date(s):
    try:
        return datetime.strptime(s.strip(), "%B %d, %Y").date().isoformat()
    except Exception:
        return s or ""


# ---------------- sources ----------------
def house_fetch(n):
    """Return (pdf_bytes, url) or (None, reason)."""
    url = HOUSE_PDF.format(c=CONGRESS, n=n)
    if not allowed(url):
        return None, "blocked by robots.txt"
    try:
        data = http_get(url)
        return (data, url) if data.startswith(b"%PDF") else (None, "not a PDF")
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}"
    except Exception as e:
        return None, f"unavailable ({type(e).__name__})"


def senate_row(d):
    """One listing record -> our metadata row."""
    m = re.search(r"(\d+)", d.get("no") or "")
    n = int(m.group(1)) if m else 0
    return {"id": f"SB-{CONGRESS}-{n}", "number": n, "system_id": str(d.get("id") or ""),
            "date_filed": iso_date(d.get("dateFiled") or ""), "short_title": clean(d.get("title")),
            "title": clean(d.get("longTitle") or d.get("title")), "author": clean(d.get("author")),
            "status": clean(d.get("legislativeStatus")).capitalize(), "status_date": iso_date(d.get("legislativeStatusDate") or ""),
            "committee": clean(d.get("primaryCommittee")), "subjects": "; ".join(clean(x) for x in (d.get("subjects") or []))}


def senate_list_page(p):
    """Return (rows, has_next) or raise."""
    url = SENATE_LIST.format(c=CONGRESS, p=p)
    if not allowed(url):
        raise PermissionError("blocked by robots.txt")
    data = json.loads(http_get(url, accept="application/json"))
    if not data.get("success"):
        raise ValueError("listing returned no data")
    return [senate_row(d) for d in data.get("data", []) if (d.get("no") or "").startswith("SBN")], \
        bool((data.get("pagination") or {}).get("has_next"))


def load_listing():
    if not SENATE_LISTING.exists():
        return {}
    with open(SENATE_LISTING, newline="", encoding="utf-8") as f:
        return {int(r["number"]): r for r in csv.DictReader(f)}


def save_listing(listing):
    SENATE_LISTING.parent.mkdir(parents=True, exist_ok=True)
    with open(SENATE_LISTING, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=LISTING_FIELDS)
        w.writeheader()
        for n in sorted(listing, reverse=True):
            w.writerow({k: listing[n].get(k, "") for k in LISTING_FIELDS})


def senate_sync(listing, delay=4.0, max_pages=40):
    """Update the listing from the newest page down. On later runs, stop at the first page with
    nothing new; status changes on older bills are refreshed by a full pass every Sunday."""
    full = not listing or datetime.now(timezone.utc).weekday() == 6
    added = 0
    for p in range(1, max_pages + 1):
        rows, has_next = senate_list_page(p)
        new_here = sum(1 for r in rows if r["number"] not in listing)
        for r in rows:
            listing[r["number"]] = r
        added += new_here
        if not has_next or (not full and new_here == 0):
            break
        time.sleep(delay)
    return added


def senate_pdf(system_id):
    """Detail record -> the bill's PDF (prefer the 'as filed' version). Returns (bytes, url) or (None, reason)."""
    url = SENATE_DETAIL.format(sid=system_id)
    if not allowed(url):
        return None, "blocked by robots.txt"
    try:
        d = json.loads(http_get(url, accept="application/json")).get("data") or {}
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}"
    except Exception as e:
        return None, f"unavailable ({type(e).__name__})"
    docs = [x for x in (d.get("documents") or []) if x.get("file_path")]
    if not docs:
        return None, "no PDF listed yet"
    doc = next((x for x in docs if "AS FILED" in (x.get("description") or "").upper()), docs[0])
    pdf_url = SENATE_PDF.format(path=urllib.request.quote(doc["file_path"]))
    if not allowed(pdf_url):
        return None, "blocked by robots.txt"
    try:
        data = http_get(pdf_url)
        return (data, pdf_url) if data.startswith(b"%PDF") else (None, "not a PDF")
    except Exception as e:
        return None, f"PDF unavailable ({type(e).__name__})"


SOURCES = {"HB": house_fetch}


# ---------------- text ----------------
def pdf_to_text(pdf_bytes, ocr=True):
    """pdftotext; OCR with tesseract when the PDF has no text layer (unless ocr=False). Returns (text, method)."""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "bill.pdf"
        p.write_bytes(pdf_bytes)
        txt = ""
        if shutil.which("pdftotext"):
            txt = subprocess.run(["pdftotext", "-layout", str(p), "-"], capture_output=True, text=True).stdout
        if len("".join(txt.split())) >= 300:
            return txt, "pdf_text"
        if ocr and shutil.which("pdftoppm") and shutil.which("tesseract"):
            subprocess.run(["pdftoppm", "-r", "300", "-gray", "-png", str(p), str(Path(d) / "pg")], check=False)
            pages = sorted(Path(d).glob("pg-*.png"), key=lambda x: int(re.findall(r"\d+", x.stem)[-1]))
            out = []
            for i, img in enumerate(pages, 1):
                out.append(f"===== [page {i}] =====")
                out.append(subprocess.run(["tesseract", str(img), "-", "-l", "eng"], capture_output=True, text=True).stdout)
            return "\n".join(out), "ocr"
        return txt, "no_text"


def title_of(text):
    """The bill's title: the first upper-case 'AN ACT ...' (bill titles are printed in capitals), so a title quoted
    in the explanatory note in ordinary case is not mistaken for it; falls back to any 'An Act' if none."""
    stop = r"(?:\n\s*\n|EXPLANATORY\s+NOTE|Be\s+it\s+enacted)"
    text = re.sub(r"\bAN\s+ACT\s*\n\s*\n", "AN ACT ", text)      # some bills print 'AN ACT' on its own line
    m = re.search(r"(AN\s+ACT\b.*?)" + stop, text, re.S) or re.search(r"(AN\s+ACT\b.*?)" + stop, text, re.S | re.I)
    return " ".join(m.group(1).split())[:600] if m else ""


def screen(title):
    """Does the title propose creating a national government entity?"""
    if not title:
        return "no title found"
    creates = re.search(r"\b(CREATING|ESTABLISHING|CREATION OF|ESTABLISHMENT OF|CONSTITUTING)\b", title, re.I)
    if creates and LOCAL_RX.search(title):
        return "local entity (excluded)"
    if not ENTITY_RX.search(title):
        return "not entity-creating"
    return "entity-creating"


# ---------------- run ----------------
def save_text(ch, n, text):
    fname = f"{ch}{n:05d}.txt" if ch == "HB" else f"SB{n}.txt"
    (TEXT / f"{CONGRESS}th Congress").mkdir(parents=True, exist_ok=True)
    (TEXT / f"{CONGRESS}th Congress" / fname).write_text(text)


def run_house(state, inbox, known, report, max_probe, stop_after, pending_days, delay, dry_run):
    ch = "HB"
    start = state["last_seen"][ch] + 1
    candidates = sorted({int(k) for k in state["pending"].get(ch, {})} | set(range(start, start + max_probe)))
    report["checked"][ch] = [candidates[0], candidates[-1]] if candidates else []
    if dry_run:
        print(f"HB: would check {len(candidates)} numbers from {candidates[0]} to {candidates[-1]}")
        return
    misses, source_errors = 0, 0
    for n in candidates:
        bid = f"{ch}-{CONGRESS}-{n}"
        if bid in known:
            continue
        data, info = SOURCES[ch](n)
        time.sleep(delay)
        if data is None:
            if info.startswith(("unavailable", "PDF unavailable", "HTTP 5")):
                source_errors += 1
            state["pending"].setdefault(ch, {}).setdefault(str(n), now())
            if n >= start:
                misses += 1
            if misses >= stop_after or source_errors >= 3:
                break
            continue
        misses = 0
        text, method = pdf_to_text(data)
        title = title_of(text)
        save_text(ch, n, text)
        item = {"id": bid, "chamber": ch, "number": n, "congress": CONGRESS, "title": title, "screen": screen(title),
                "text": "saved", "text_method": method, "source_url": info, "found": now(), "status": "new"}
        inbox.append(item)
        known.add(bid)
        report["found"].append({k: item[k] for k in ("id", "screen", "title")})
        state["pending"].get(ch, {}).pop(str(n), None)
        state["last_seen"][ch] = max(state["last_seen"][ch], n)
    if source_errors >= 3:
        report["errors"][ch] = "source unavailable: check failed, NOT the same as 'no new bills'"
    cutoff = datetime.now(timezone.utc) - timedelta(days=pending_days)
    state["pending"][ch] = {k: v for k, v in state["pending"].get(ch, {}).items() if datetime.fromisoformat(v) > cutoff}


def run_senate(state, inbox, known, report, max_pdfs, delay, dry_run, recent_days=45):
    """New = filed in the last `recent_days` days, or older but in the pilot scope (so its text is fetched).
    Every other Senate bill stays in the listing, which the portal shows in full."""
    ch = "SB"
    if dry_run:
        print(f"SB: would sync the Senate listing and fetch up to {max_pdfs} new bill texts after SBN {state['last_seen'][ch]}")
        return
    listing = load_listing()
    try:
        added = senate_sync(listing, delay=delay)
        save_listing(listing)
        report["senate_listing"] = {"bills": len(listing), "added": added}
    except Exception as e:
        report["errors"][ch] = f"source unavailable ({type(e).__name__}: {e}): check failed, NOT the same as 'no new bills'"
        return
    floor = state["last_seen"][ch]
    state["pending"].pop(ch, None)          # the Senate listing replaces number probing
    recent = (datetime.now(timezone.utc) - timedelta(days=recent_days)).date().isoformat()
    for n, r in sorted(listing.items()):
        if n > floor and r["id"] not in known and (r["date_filed"] >= recent or screen(r["title"]) == PILOT):
            item = {"id": r["id"], "chamber": ch, "number": n, "congress": CONGRESS, "title": r["title"],
                    "short_title": r["short_title"], "date_filed": r["date_filed"], "legislative_status": r["status"],
                    "screen": screen(r["title"]), "text": "pending", "attempts": 0, "system_id": r["system_id"],
                    "source_url": f"{SENATE}/legislative-documents/bills/{r['system_id']}", "found": now(), "status": "new"}
            inbox.append(item)
            known.add(r["id"])
            report["found"].append({k: item[k] for k in ("id", "screen", "title")})
    if listing:
        state["last_seen"][ch] = max(state["last_seen"][ch], max(listing))
    # bill texts: pilot-scope first, then newest; failures retried on later runs (up to 5 tries)
    todo = [x for x in inbox if x["chamber"] == ch and x.get("text") == "pending" and x.get("attempts", 0) < 5]
    todo.sort(key=lambda x: (x["screen"] != PILOT, -x["number"]))
    fetched, source_errors = 0, 0
    for x in todo[:max_pdfs]:
        data, info = senate_pdf(x.get("system_id"))
        time.sleep(delay)
        x["attempts"] = x.get("attempts", 0) + 1
        if data is None:
            x["text_note"] = info
            if info.startswith(("unavailable", "PDF unavailable", "HTTP 5")):
                source_errors += 1
                if source_errors >= 3:
                    report["errors"][ch] = "bill texts unavailable: listing synced, PDFs will be retried"
                    break
            continue
        text, method = pdf_to_text(data)
        save_text(ch, x["number"], text)
        x.update({"text": "saved", "text_method": method, "pdf_url": info})
        x.pop("text_note", None)
        fetched += 1
    report["senate_texts"] = {"fetched": fetched, "still_pending": sum(1 for x in inbox if x["chamber"] == ch and x.get("text") == "pending")}


def known_house_numbers():
    """20th Congress House bill numbers already listed (Open Congress Data index, corpus)."""
    import gzip
    nums = set()
    idx = ROOT / "data" / "processed" / "bill_index.csv.gz"
    if idx.exists():
        with gzip.open(idx, "rt", encoding="utf-8") as f:
            for r in csv.DictReader(f):
                if r.get("chamber") == "HB" and r.get("congress") == CONGRESS and r.get("number", "").isdigit():
                    nums.add(int(r["number"]))
    try:
        from pipeline.compare import load
        for b in load()[0].values():
            if b.get("chamber") == "HB" and b.get("congress") == CONGRESS:
                nums.add(int(b["id"].split("-")[2]))
    except Exception:
        pass
    return nums


def run_backfill(state, inbox, known, report, max_n, delay, dry_run):
    """Catch-up: work backwards through House numbers that are missing from every list, fetching each
    bill from the House documents server. Runs alongside the daily check; up to max_n numbers per run."""
    if max_n <= 0:
        return
    bf = state.setdefault("backfill", {"next": state["last_seen"]["HB"], "absent": []})
    listed = known_house_numbers() | {int(x["number"]) for x in inbox if x["chamber"] == "HB"}
    absent = set(bf.get("absent", []))
    todo, n = [], bf["next"]
    while n >= 1 and len(todo) < max_n:
        if n not in listed and n not in absent:
            todo.append(n)
        n -= 1
    report["backfill"] = {"checked": [todo[0], todo[-1]] if todo else [], "remaining": sum(
        1 for k in range(1, n + 1) if k not in listed and k not in absent)}
    if dry_run:
        print(f"HB catch-up: would check {len(todo)} missing numbers from {todo[:1]} down to {todo[-1:]}")
        return
    found, errors = 0, 0
    for k in todo:
        data, info = SOURCES["HB"](k)
        time.sleep(delay)
        if data is None:
            if info.startswith(("unavailable", "HTTP 5")):
                errors += 1
                if errors >= 5:
                    report["errors"]["HB catch-up"] = "House documents server unavailable; catch-up will resume next run"
                    return
                continue
            absent.add(k)                     # not on the server (withdrawn, or never uploaded)
            bf["next"] = k - 1
            continue
        text, method = pdf_to_text(data, ocr=False)
        title = title_of(text)
        if method != "no_text":
            save_text("HB", k, text)
        bid = f"HB-{CONGRESS}-{k}"
        inbox.append({"id": bid, "chamber": "HB", "number": k, "congress": CONGRESS, "title": title, "screen": screen(title),
                      "text": "saved" if method != "no_text" else "scanned (OCR pending)", "text_method": method,
                      "source_url": info, "found": now(), "status": "new", "backfill": True})
        known.add(bid)
        found += 1
        bf["next"] = k - 1
    bf["absent"] = sorted(absent)
    report["backfill"]["added"] = found


def run(max_probe=60, stop_after=8, pending_days=21, delay=4.0, dry_run=False, chambers=("HB", "SB"), max_pdfs=25, backfill=150):
    WATCH.mkdir(parents=True, exist_ok=True)
    state = load_json(STATE, None) or initial_state()
    inbox = load_json(INBOX, [])
    for x in inbox:                     # older runs used "not for review" for bills outside the pilot scope
        if x.get("status") == "not for review":
            x["status"] = "new"
        x.setdefault("text", "saved")
    for x in inbox:                     # re-read titles that look wrong (empty, too short, or not the capitalised title)
        if x["chamber"] == "HB" and x.get("text") == "saved" and (len(x.get("title", "")) < 20 or not x.get("title", "").isupper()):
            f = TEXT / f"{x['congress']}th Congress" / f"HB{int(x['number']):05d}.txt"
            if f.exists():
                new = title_of(f.read_text(errors="ignore"))
                if new and new != x.get("title"):
                    x["title"], x["screen"] = new, screen(new)
    known = {x["id"] for x in inbox}
    report = {"time": now(), "checked": {}, "found": [], "errors": {}}
    if "HB" in chambers:
        run_house(state, inbox, known, report, max_probe, stop_after, pending_days, delay, dry_run)
    if "SB" in chambers:
        run_senate(state, inbox, known, report, max_pdfs, delay, dry_run)
    if "HB" in chambers:
        run_backfill(state, inbox, known, report, backfill, delay, dry_run)
    if not dry_run:
        summary = {k: report[k] for k in ("time", "checked", "errors")} | {"found": len(report["found"])}
        if report.get("backfill"):
            summary["catch_up_added"] = report["backfill"].get("added", 0)
            summary["catch_up_remaining"] = report["backfill"].get("remaining")
        summary["pilot_scope"] = sum(1 for f in report["found"] if f["screen"] == PILOT)
        state["runs"] = (state.get("runs", []) + [summary])[-60:]
        STATE.write_text(json.dumps(state, indent=1))
        INBOX.write_text(json.dumps(inbox, indent=1, ensure_ascii=False))
    return report


def triage():
    """Run TrAIce on new pilot-scope bills (needs ANTHROPIC_API_KEY); save briefs for the inbox."""
    from agents import llm
    if not llm.api_key():
        print("No API key: skipping TrAIce triage (the reviewer can run it from the portal).")
        return
    from agents.research import run_agent
    inbox = load_json(INBOX, [])
    out_dir = WATCH / "briefs"
    out_dir.mkdir(parents=True, exist_ok=True)
    for item in inbox:
        if (item["status"] == "new" and item.get("screen") == PILOT and item.get("text", "saved") == "saved"
                and not (out_dir / f"{item['id']}.json").exists()):
            try:
                res = run_agent(item["id"])
                (out_dir / f"{item['id']}.json").write_text(json.dumps({"output": res["output"], "checks": res["checks"]}, ensure_ascii=False))
                item["status"] = "triaged"
            except Exception as e:
                print(f"{item['id']}: triage failed ({e})")
    INBOX.write_text(json.dumps(inbox, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--max-probe", type=int, default=60)
    ap.add_argument("--max-pdfs", type=int, default=25, help="Senate bill texts to download per run")
    ap.add_argument("--stop-after", type=int, default=8)
    ap.add_argument("--backfill", type=int, default=150, help="missing older House numbers to catch up per run (0 to skip)")
    ap.add_argument("--delay", type=float, default=4.0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--chamber", choices=["HB", "SB"])
    ap.add_argument("--triage", action="store_true", help="after the run, rebuild the corpus and run Agent 1 on new bills")
    a = ap.parse_args()
    rep = run(a.max_probe, a.stop_after, delay=max(2.0, a.delay), dry_run=a.dry_run, chambers=(a.chamber,) if a.chamber else ("HB", "SB"), max_pdfs=a.max_pdfs, backfill=a.backfill)
    print(json.dumps(rep, indent=1, ensure_ascii=False))
    if a.triage and not a.dry_run:
        subprocess.run(["python", "-m", "pipeline.build_corpus"], cwd=ROOT, check=False)
        triage()
