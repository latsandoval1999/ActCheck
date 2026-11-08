"""Download bill PDFs from the House and Senate websites, politely.

Run this on your own computer (it needs normal internet access):

    python -m pipeline.fetch_bills --list-families            # see family IDs
    python -m pipeline.fetch_bills --family F001 --dry-run     # show what would be downloaded
    python -m pipeline.fetch_bills --family F001 F002          # download two families
    python -m pipeline.fetch_bills --tier A --congress 20      # every tier-A family, 20th Congress only
    python -m pipeline.fetch_bills --all --limit 200           # everything, at most 200 files this run

Links come from data/processed/family_bills.csv (built from Open Congress Data).
Files already present (in the output folder or the existing corpus) are skipped,
so you can stop and rerun at any time. Every attempt is recorded in
<out>/download_log.csv for your data inventory.

Etiquette: one request at a time, a pause between requests (default 4 s),
robots.txt respected, and a clear user agent. Please keep it that way.
"""
import argparse
import csv
import hashlib
import re
import sys
import time
import urllib.error
import urllib.request
import urllib.robotparser
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
INDEX = ROOT / "data" / "processed" / "family_bills.csv"
DEFAULT_OUT = ROOT.parent / "PP5538 Bill Corpus" / "6 Downloads"
EXISTING = ROOT.parent / "PP5538 Bill Corpus"
USER_AGENT = "PP5538-student-research-bill-fetcher/1.0 (academic, non-commercial; one request every few seconds)"

_robots = {}


def _read_robots(host):
    """Return (parser or None, note). Follows RFC 9309:
    2xx -> obey the file; 4xx (except 429) -> no robots.txt, so no restrictions;
    5xx, 429 or unreachable -> assume everything is disallowed."""
    req = urllib.request.Request(host + "/robots.txt", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            lines = r.read().decode("utf-8", errors="ignore").splitlines()
        rp = urllib.robotparser.RobotFileParser()
        rp.parse(lines)
        signals = sorted({ln.strip() for ln in lines if ln.lower().startswith("content-signal")})
        return rp, "robots.txt found" + (f"; {'; '.join(signals)}" if signals else "")
    except urllib.error.HTTPError as e:
        if 400 <= e.code < 500 and e.code != 429:
            return None, f"no robots.txt (HTTP {e.code}): no restrictions under RFC 9309"
        return False, f"robots.txt unavailable (HTTP {e.code}): not downloading from this host"
    except Exception as e:
        hint = ""
        if "CERTIFICATE" in str(e).upper():
            hint = (" -- Python cannot verify website certificates. On a Mac with Python from python.org, run "
                    "'Install Certificates.command' in Applications/Python 3.x, then try again.")
        return False, f"robots.txt unreachable ({type(e).__name__}: {str(e)[:120]}): not downloading from this host{hint}"


def allowed(url):
    host = "{0.scheme}://{0.netloc}".format(urlparse(url))
    if host not in _robots:
        rp, note = _read_robots(host)
        _robots[host] = rp
        print(f"{host}: {note}")
    rp = _robots[host]
    if rp is None:
        return True
    if rp is False:
        return False
    return rp.can_fetch(USER_AGENT, url)


def safe(name):
    return re.sub(r"[^A-Za-z0-9 \-]+", "", name)[:60].strip()


def load_index():
    with open(INDEX, newline="") as f:
        return list(csv.DictReader(f))


def existing_files():
    return {p.name.upper() for p in EXISTING.rglob("*.pdf")} if EXISTING.exists() else set()


def fetch(url, dest, retries=2, timeout=60):
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    for attempt in range(retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as r:
                data = r.read()
            if not data.startswith(b"%PDF"):
                return "not a PDF (page may have moved)", 0, ""
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)
            return "downloaded", len(data), hashlib.sha256(data).hexdigest()
        except urllib.error.HTTPError as e:
            if e.code == 404:
                return "not found (404)", 0, ""
            err = f"HTTP {e.code}"
        except Exception as e:  # network hiccup
            err = f"{type(e).__name__}: {str(e)[:100]}"
        time.sleep(10 * (attempt + 1))
    return f"failed ({err})", 0, ""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--family", nargs="*", default=[], help="family IDs, e.g. F001 F014")
    ap.add_argument("--tier", choices=["A", "B", "C"], help="all families in a review tier")
    ap.add_argument("--all", action="store_true", help="all families (excluding 'Excluded' and 'Check' rows)")
    ap.add_argument("--congress", nargs="*", default=[], help="limit to Congress numbers, e.g. 20 19")
    ap.add_argument("--chamber", choices=["HB", "SB"], help="House or Senate only")
    ap.add_argument("--limit", type=int, default=0, help="stop after this many downloads")
    ap.add_argument("--delay", type=float, default=4.0, help="seconds between requests (min 2)")
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--dry-run", action="store_true")
    ap.add_argument("--list-families", action="store_true")
    a = ap.parse_args(argv)

    rows = load_index()
    if a.list_families:
        seen = {}
        for r in rows:
            seen.setdefault(r["family_id"], [r["family_entity"], r["tier"], 0])[2] += 1
        for fid, (ent, tier, n) in seen.items():
            print(f"{fid}  {n:>3} bills  {tier[:30]:<30}  {ent}")
        return

    pick = rows
    if a.family:
        pick = [r for r in pick if r["family_id"] in set(a.family)]
    elif a.tier:
        pick = [r for r in pick if r["tier"].startswith(a.tier + ":")]
    elif a.all:
        pick = [r for r in pick if not r["tier"].startswith(("Excluded", "Check"))]
    else:
        ap.error("choose --family, --tier, --all or --list-families")
    if a.congress:
        pick = [r for r in pick if r["congress"] in set(a.congress)]
    if a.chamber:
        pick = [r for r in pick if r["chamber"] == a.chamber]

    have = existing_files()
    todo = []
    for r in pick:
        dest = a.out / f"{r['family_id']} {safe(r['family_entity'])}" / f"{r['congress']}th" / r["file_name"]
        if dest.exists() or (r["congress"] == "20" and r["file_name"].upper() in have):
            continue
        if not r["pdf_url"]:
            print(f"no link for {r['chamber']} {r['number']} ({r['congress']}th): skip")
            continue
        todo.append((r, dest))
    print(f"{len(pick)} bills selected, {len(pick) - len(todo)} already present or without link, {len(todo)} to download")
    if a.limit:
        todo = todo[: a.limit]
    if a.dry_run:
        for r, dest in todo:
            print(f"would fetch {r['pdf_url']}  ->  {dest}")
        return

    a.out.mkdir(parents=True, exist_ok=True)
    log_path = a.out / "download_log.csv"
    new_log = not log_path.exists()
    delay = max(2.0, a.delay)
    with open(log_path, "a", newline="") as lf:
        log = csv.writer(lf)
        if new_log:
            log.writerow(["time_utc", "family_id", "chamber", "congress", "number", "url", "file", "result", "bytes", "sha256"])
        for i, (r, dest) in enumerate(todo, 1):
            if not allowed(r["pdf_url"]):
                host = "{0.scheme}://{0.netloc}".format(urlparse(r["pdf_url"]))
                why = "host skipped (see message above)" if _robots.get(host) is False else "disallowed by robots.txt"
                result, size, digest = why, 0, ""
            else:
                result, size, digest = fetch(r["pdf_url"], dest)
            log.writerow([datetime.now(timezone.utc).isoformat(timespec="seconds"), r["family_id"], r["chamber"],
                          r["congress"], r["number"], r["pdf_url"], str(dest.relative_to(a.out)), result, size, digest])
            lf.flush()
            print(f"[{i}/{len(todo)}] {r['chamber']} {r['number']} ({r['congress']}th): {result}")
            time.sleep(delay)
    print(f"Done. Log: {log_path}")


if __name__ == "__main__":
    sys.exit(main())
