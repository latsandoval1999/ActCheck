"""Build the two search indexes Agent 1 uses beyond the bill corpus.

1. data/processed/bill_index.csv.gz  -- every House and Senate bill, 18th-20th
   Congress (number, title, date filed, status, PDF link), from Open Congress Data.
2. data/processed/law_index.csv.gz   -- every Republic Act, Presidential Decree,
   Executive Order, Commonwealth Act, Batas Pambansa and Act in the Philippine
   Legal Documents Library (id, type, number, year, title), from Lawphil via BetterGov.

Run on the computer that has both folders:
    python -m pipeline.build_indexes --open-congress "../../Open Congress" --legal-docs "../../Legal Docs_Markdown"

Add full law texts to the corpus (so Agent 1 can quote them):
    python -m pipeline.build_indexes --legal-docs "../../Legal Docs_Markdown" --shelf RA-7160 EO-292
"""
import argparse
import csv
import gzip
import os
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"
SHELF = ROOT / "data" / "raw_text" / "4 Existing laws"

LAW_DIRS = {"repacts": "RA", "presdecs": "PD", "execord": "EO", "comacts": "CA", "bataspam": "BP", "acts": "ACT"}
LAW_FILE = re.compile(r"^([a-z]+)_(\d+[a-z\-]*)_(\d{4})\.md$")


def _toml_get(key, s):
    m = re.search(r'^' + key + r'\s*=\s*"((?:[^"\\]|\\.)*)"', s, re.M)
    return m.group(1).replace('\\"', '"') if m else ""


def bill_index(open_congress):
    rows = []
    base = Path(open_congress) / "data" / "document"
    for ch in ("hb", "sb"):
        for c in ("18", "19", "20"):
            d = base / ch / c
            if not d.exists():
                continue
            for f in d.glob("*.toml"):
                s = f.read_text(encoding="utf-8", errors="ignore")
                num = re.search(r"^bill_number\s*=\s*(\d+)", s, re.M)
                title = _toml_get("congress_website_title", s) or _toml_get("long_title", s)
                st = re.findall(r'^status\s*=\s*"(.*)"', s, re.M)
                url = re.search(r'download_url_sources\s*=\s*\["([^"]+)', s)
                rows.append({"id": f"{ch.upper()}-{c}-{num.group(1) if num else ''}", "chamber": ch.upper(), "congress": c,
                             "number": num.group(1) if num else "", "date_filed": _toml_get("date_filed", s),
                             "short_title": _toml_get("title", s) if ch == "sb" else "", "title": " ".join(title.split()),
                             "status": st[-1] if st else "", "pdf_url": url.group(1) if url else ""})
    return rows


def _law_title(head, kind):
    h = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", head)          # drop markdown links
    h = " ".join(h.replace("*", " ").replace("\ufffd", "N").split())
    m = re.search(r"\bAN ACT\b", h, re.I)
    if m:
        t = h[m.start():]
        t = re.split(r"\s(?:Be it enacted|WHEREAS|SECTION 1\b|Section 1\b)", t, maxsplit=1)[0]
        return t[:400].strip()
    m = re.search(r"(?:DECREE|ORDER|PROCLAMATION|ACT)\s+No\.?\s*[\w\-]+,?\s*(?:\w+\s+\d{1,2},\s+\d{4})?\s*\]?\s*(.{10,300})", h, re.I)
    t = m.group(1) if m else h
    t = re.split(r"\s(?:WHEREAS|NOW, THEREFORE|Section 1\b|SECTION 1\b)", t, maxsplit=1)[0]
    return t[:300].strip()


def law_index(legal_docs=None, titles_csv=None):
    rows = []
    if titles_csv:  # fast path: the heads file built earlier
        src = ((r["path"], r["head"]) for r in csv.DictReader(open(titles_csv, encoding="utf-8")))
    else:
        def gen():
            for d in LAW_DIRS:
                for p in Path(legal_docs, d).rglob("*.md"):
                    yield str(p.relative_to(legal_docs)), p.read_text(encoding="utf-8", errors="ignore")[:2500]
        src = gen()
    for path, head in src:
        top = path.split("/")[0]
        m = LAW_FILE.match(os.path.basename(path))
        if top not in LAW_DIRS or not m:
            continue
        kind = LAW_DIRS[top]
        num = m.group(2).upper()
        lid = f"{kind}-{num}" if kind in ("RA", "PD", "BP", "CA") else f"{kind}-{num}-{m.group(3)}"
        rows.append({"id": lid, "type": kind, "number": m.group(2).upper(), "year": m.group(3),
                     "title": _law_title(head, kind)[:400], "path": path})
    seen, out = set(), []
    for r in rows:
        if r["id"] not in seen:
            seen.add(r["id"])
            out.append(r)
    return out


def write_gz(rows, path):
    PROC.mkdir(parents=True, exist_ok=True)
    with gzip.open(path, "wt", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(rows[0].keys()))
        w.writeheader()
        w.writerows(rows)
    print(f"{path.name}: {len(rows)} rows")


def shelf(legal_docs, ids):
    idx = {r["id"]: r for r in law_index(legal_docs=legal_docs)}
    SHELF.mkdir(parents=True, exist_ok=True)
    for i in ids:
        r = idx.get(i.upper())
        if not r:
            print(f"{i}: not found in the library")
            continue
        text = Path(legal_docs, r["path"]).read_text(encoding="utf-8", errors="ignore")
        (SHELF / f"{r['id']}.txt").write_text(text)
        print(f"{i}: added ({r['title'][:70]})")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--open-congress")
    ap.add_argument("--legal-docs")
    ap.add_argument("--law-titles-csv", help="use a pre-built heads CSV instead of reading the library")
    ap.add_argument("--shelf", nargs="*", help="law IDs to copy into the corpus, e.g. RA-7160 PD-1067")
    a = ap.parse_args()
    if a.shelf:
        shelf(a.legal_docs, a.shelf)
        return
    if a.open_congress:
        rows = bill_index(a.open_congress)
        old = PROC / "bill_index.csv.gz"
        n_old = sum(1 for _ in gzip.open(old, "rt")) - 1 if old.exists() else 0
        if len(rows) < 0.95 * n_old:      # a partial download must not shrink the list
            print(f"Kept the existing bill index: new copy has {len(rows)} bills, existing has {n_old}.")
        else:
            write_gz(rows, old)
            print(f"Bill index: {len(rows)} bills (was {n_old}).")
    if a.legal_docs or a.law_titles_csv:
        write_gz(law_index(a.legal_docs, a.law_titles_csv), PROC / "law_index.csv.gz")


if __name__ == "__main__":
    main()
