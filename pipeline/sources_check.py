"""Check each data source ActCheck relies on, from wherever this runs (the daily GitHub job), and record the
result in data/watch/sources.json for the Run log. A blocked source is reported as blocked, never bypassed.

    python -m pipeline.sources_check
"""
import json
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

from pipeline.fetch_bills import USER_AGENT

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "data" / "watch" / "sources.json"

SOURCES = [
    ("House of Representatives: legislative documents page", "https://www.congress.gov.ph/legislative-documents",
     "Bot check (Cloudflare) blocks automated visitors; ActCheck uses the House documents server below instead"),
    ("House of Representatives: documents server (bill PDFs)", "https://docs.congress.hrep.online/legisdocs/basic_20/HB00001.pdf",
     "Source of new House bills in the daily check"),
    ("Senate: bill listing", "https://senate.gov.ph/lis/documents_v2?document_type=bills&congress=20th+Congress&type=SBN&sort_by=no&sort_order=desc&page=1&per_page=1",
     "Source of new Senate bills; its firewall refuses GitHub's servers"),
    ("BetterGov.PH Open Congress Data (dataset 4)", "https://github.com/bettergovph/open-congress-data",
     "Historical House and Senate bill list, 18th-20th Congress (CC0)"),
    ("BetterGov.PH Philippine Legal Documents Library (dataset 24)", "https://huggingface.co/datasets/bettergovph/gov-library/resolve/main/repacts_with_summary.parquet",
     "Republic Acts with summaries and origin bills (CC BY-NC 4.0), refreshed weekly"),
]


def check(url):
    req = urllib.request.Request(url, method="HEAD" if url.endswith((".pdf", ".parquet")) else "GET", headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.status, "reachable"
    except urllib.error.HTTPError as e:
        body = ""
        try:
            body = e.read(2000).decode("utf-8", "ignore")
        except Exception:
            pass
        why = "bot check (Cloudflare challenge)" if "challenge" in body.lower() or "just a moment" in body.lower() else "refused"
        return e.code, why
    except Exception as e:
        return None, f"no connection ({type(e).__name__})"


def main():
    now = datetime.now(timezone.utc).isoformat(timespec="seconds")
    rows = []
    for name, url, role in SOURCES:
        code, status = check(url)
        rows.append({"time": now, "source": name, "url": url, "http": code, "status": status, "role": role})
        print(f"{code} {status:35} {name}")
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(rows, indent=1))


if __name__ == "__main__":
    main()
