"""Daily watcher (TrAIce's monitoring step): find newly filed bills, keep the ones that
propose creating a government entity, fetch and read them, and put them in the reviewer's inbox.

How it finds new bills (politely, without bypassing any site protection):
  * House: checks the House legislative-documents PDF server for the next bill numbers after
    the highest one already seen (docs.congress.hrep.online/legisdocs/basic_20/HB#####.pdf).
    The congress.gov.ph listing pages use a bot challenge, so they are not scraped.
  * Senate: checks the public bill page for the next SBN numbers
    (web.senate.gov.ph/lis/bill_res.aspx?congress=20&q=SBN-####) and follows its PDF link.
    The Senate site was unreachable when this was written (8 Nov 2026), so this adapter is
    UNTESTED; a failure is reported as "source unavailable", never as "no new bills".

Each run:
  1. probes up to --max-probe numbers per chamber; stops after --stop-after consecutive misses;
     missing numbers are re-checked on later runs for --pending-days days (PDFs are often late)
  2. reads the title from the first page and screens it with the entity-creation rules
  3. saves text (pdftotext, OCR with tesseract if the PDF is scanned) under data/raw_text/_watch/
  4. records everything in data/watch/inbox.json (status: new / not entity / no text yet)
  5. optional --triage: runs Agent 1 on each new entity bill if ANTHROPIC_API_KEY is set

    python -m pipeline.watch                 # one run (then: python -m pipeline.build_corpus)
    python -m pipeline.watch --dry-run       # list what would be checked
"""
import argparse
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
SENATE_PAGE = "https://web.senate.gov.ph/lis/bill_res.aspx?congress={c}&q=SBN-{n}"
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


def http_get(url, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


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


def senate_fetch(n):
    page = SENATE_PAGE.format(c=CONGRESS, n=n)
    if not allowed(page):
        return None, "blocked by robots.txt"
    try:
        html = http_get(page).decode("utf-8", errors="ignore")
    except urllib.error.HTTPError as e:
        return None, f"HTTP {e.code}"
    except Exception as e:
        return None, f"unavailable ({type(e).__name__})"
    m = re.search(r'href="([^"]*lisdata/[^"]+\.pdf)"', html, re.I)
    if not m:
        return None, "no PDF link on bill page"
    pdf_url = m.group(1) if m.group(1).startswith("http") else "https://web.senate.gov.ph/lis/" + m.group(1).lstrip("./")
    try:
        data = http_get(pdf_url)
        return (data, pdf_url) if data.startswith(b"%PDF") else (None, "not a PDF")
    except Exception as e:
        return None, f"PDF unavailable ({type(e).__name__})"


SOURCES = {"HB": house_fetch, "SB": senate_fetch}


# ---------------- text ----------------
def pdf_to_text(pdf_bytes):
    """pdftotext; OCR with tesseract when the PDF has no text layer. Returns (text, method)."""
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "bill.pdf"
        p.write_bytes(pdf_bytes)
        txt = ""
        if shutil.which("pdftotext"):
            txt = subprocess.run(["pdftotext", "-layout", str(p), "-"], capture_output=True, text=True).stdout
        if len("".join(txt.split())) >= 300:
            return txt, "pdf_text"
        if shutil.which("pdftoppm") and shutil.which("tesseract"):
            subprocess.run(["pdftoppm", "-r", "300", "-gray", "-png", str(p), str(Path(d) / "pg")], check=False)
            pages = sorted(Path(d).glob("pg-*.png"), key=lambda x: int(re.findall(r"\d+", x.stem)[-1]))
            out = []
            for i, img in enumerate(pages, 1):
                out.append(f"===== [page {i}] =====")
                out.append(subprocess.run(["tesseract", str(img), "-", "-l", "eng"], capture_output=True, text=True).stdout)
            return "\n".join(out), "ocr"
        return txt, "no_text"


def title_of(text):
    m = re.search(r"(AN\s+ACT\b.*?)(?:\n\s*\n|EXPLANATORY\s+NOTE|Be\s+it\s+enacted)", text, re.S | re.I)
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
def run(max_probe=30, stop_after=8, pending_days=21, delay=4.0, dry_run=False, chambers=("HB", "SB")):
    WATCH.mkdir(parents=True, exist_ok=True)
    state = load_json(STATE, None) or initial_state()
    inbox = load_json(INBOX, [])
    known = {x["id"] for x in inbox}
    report = {"time": now(), "checked": {}, "found": [], "errors": {}}
    for ch in chambers:
        start = state["last_seen"][ch] + 1
        candidates = sorted({int(k) for k, v in state["pending"].get(ch, {}).items()} | set(range(start, start + max_probe)))
        report["checked"][ch] = [candidates[0], candidates[-1]] if candidates else []
        if dry_run:
            print(f"{ch}: would check {len(candidates)} numbers from {candidates[0]} to {candidates[-1]}")
            continue
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
            verdict = screen(title)
            fname = f"{ch}{n:05d}.txt" if ch == "HB" else f"SB{n}.txt"
            (TEXT / f"{CONGRESS}th Congress").mkdir(parents=True, exist_ok=True)
            (TEXT / f"{CONGRESS}th Congress" / fname).write_text(text)
            item = {"id": bid, "chamber": ch, "number": n, "congress": CONGRESS, "title": title, "screen": verdict,
                    "text_method": method, "source_url": info, "found": now(),
                    "status": "new" if verdict == "entity-creating" else "not for review"}
            inbox.append(item)
            known.add(bid)
            report["found"].append({k: item[k] for k in ("id", "screen", "title")})
            state["pending"].get(ch, {}).pop(str(n), None)
            state["last_seen"][ch] = max(state["last_seen"][ch], n)
        if source_errors >= 3:
            report["errors"][ch] = "source unavailable: check failed, NOT the same as 'no new bills'"
        cutoff = datetime.now(timezone.utc) - timedelta(days=pending_days)
        state["pending"][ch] = {k: v for k, v in state["pending"].get(ch, {}).items()
                                if datetime.fromisoformat(v) > cutoff}
    if not dry_run:
        state["runs"] = (state.get("runs", []) + [{k: report[k] for k in ("time", "checked", "errors")} | {"found": len(report["found"])}])[-60:]
        STATE.write_text(json.dumps(state, indent=1))
        INBOX.write_text(json.dumps(inbox, indent=1, ensure_ascii=False))
    return report


def triage():
    """Run Agent 1 on new entity-creating bills (needs ANTHROPIC_API_KEY); save briefs for the inbox."""
    from agents import llm
    if not llm.api_key():
        print("No API key: skipping TrAIce triage (the reviewer can run it from the portal).")
        return
    from agents.research import run_agent
    inbox = load_json(INBOX, [])
    out_dir = WATCH / "briefs"
    out_dir.mkdir(parents=True, exist_ok=True)
    for item in inbox:
        if item["status"] == "new" and not (out_dir / f"{item['id']}.json").exists():
            try:
                res = run_agent(item["id"])
                (out_dir / f"{item['id']}.json").write_text(json.dumps({"output": res["output"], "checks": res["checks"]}, ensure_ascii=False))
                item["status"] = "triaged"
            except Exception as e:
                print(f"{item['id']}: triage failed ({e})")
    INBOX.write_text(json.dumps(inbox, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--max-probe", type=int, default=30)
    ap.add_argument("--stop-after", type=int, default=8)
    ap.add_argument("--delay", type=float, default=4.0)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--chamber", choices=["HB", "SB"])
    ap.add_argument("--triage", action="store_true", help="after the run, rebuild the corpus and run Agent 1 on new bills")
    a = ap.parse_args()
    rep = run(a.max_probe, a.stop_after, delay=max(2.0, a.delay), dry_run=a.dry_run, chambers=(a.chamber,) if a.chamber else ("HB", "SB"))
    print(json.dumps(rep, indent=1, ensure_ascii=False))
    if a.triage and not a.dry_run:
        subprocess.run(["python", "-m", "pipeline.build_corpus"], cwd=ROOT, check=False)
        triage()
