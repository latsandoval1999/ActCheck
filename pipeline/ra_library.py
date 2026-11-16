"""Republic Acts with summaries from the BetterGov.PH Philippine Legal Documents Library (dataset 24;
huggingface.co/datasets/bettergovph/gov-library, CC BY-NC 4.0, from Lawphil.net, Arellano Law Foundation).

Writes data/processed/ra_summaries.csv.gz (one row per Republic Act: number, title, date, origin bill, purpose,
summary, laws affected) and adds any Republic Act missing from data/processed/law_index.csv.gz, so TrAIce can
find existing laws a bill touches and the bills that became law.

    python -m pipeline.ra_library <repacts_with_summary.parquet>
"""
import datetime
import re
import sys
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"

WANT = {"number": r"(^|_)(ra_?)?(number|no|law_number)$", "title": r"^title$", "date": r"date|enact|approv",
        "bill": r"^(origin_|source_)?bills?(_no|_number)?$|house_bill|senate_bill", "purpose": r"purpose", "summary": r"^(overall_)?summary$", "affected": r"affect|amend",
        "tags": r"tag|keyword"}


def pick(cols, rx):
    for c in cols:
        if re.search(rx, c, re.I):
            return c
    return None


def flat(v, n=600):
    if v is None or (isinstance(v, float) and pd.isna(v)):
        return ""
    if hasattr(v, "tolist"):
        v = v.tolist()
    if isinstance(v, (list, tuple)):
        v = "; ".join(flat(x, 200) for x in v)
    elif isinstance(v, dict):
        v = "; ".join(f"{k}: {flat(x, 200)}" for k, x in v.items())
    s = " ".join(str(v).split())
    return s[:n]


MON = {m: i for i, m in enumerate(["january", "february", "march", "april", "may", "june", "july", "august", "september",
                                    "october", "november", "december"], 1)}
CONGRESS_START = ((datetime.date(2025, 7, 28), 20), (datetime.date(2022, 7, 25), 19), (datetime.date(2019, 7, 22), 18),
                  (datetime.date(2016, 7, 25), 17), (datetime.date(2013, 7, 22), 16))


def _date(s):
    for m in re.finditer(r"([A-Z][a-z]+)\s+(\d{1,2}),\s*(\d{4})", s or ""):
        if m.group(1).lower() in MON:
            return datetime.date(int(m.group(3)), MON[m.group(1).lower()], int(m.group(2)))
    return None


def origin_bills(text):
    """From the closing note of a Republic Act ("This Act, which is a consolidation of Senate Bill No. 1850 and House Bill
    No. 6336, was passed ... on March 22, 2023."): the bills it came from, the Congress that passed them, and the dates."""
    t = (text or "").replace("\xa0", " ")
    s = " ".join(re.findall(r"This\s+Act[^|]{0,500}?(?:House|Senate)\s+Bills?[^|]{0,600}?\d{4}\s*\.", t)) or \
        " ".join(re.findall(r"[^|]{0,300}(?:House|Senate)\s+Bills?\s+No[^|]{0,400}?\d{4}\s*\.", t[-6000:]))
    bills = []
    for ch, nums in re.findall(r"(House|Senate)\s+Bills?\s+Nos?\.?\s*((?:\d+[,\s]*(?:and\s+)?)+)", s):
        bills += [("HB" if ch == "House" else "SB", n) for n in re.findall(r"\d+", nums)]
    passed, approved = _date(s), _date(t[:600])
    ref = passed or approved
    c = next((k for start, k in CONGRESS_START if ref and ref >= start), None)
    return [f"{ch}-{c}-{n}" for ch, n in dict.fromkeys(bills)] if c else [], c, passed, approved


def write_origins(df):
    """data/processed/ra_origin_bills.csv: Republic Act -> the House and Senate bills it was enacted from."""
    num = pick(df.columns, WANT["number"])
    rows = []
    for _, r in df.iterrows():
        n = re.search(r"\d+", str(r[num])) if num else None
        bills, c, passed, approved = origin_bills(r.get("content", ""))
        if n and bills:
            rows.append({"ra": int(n.group()), "approved": approved.isoformat() if approved else "", "passed": passed.isoformat() if passed else "",
                         "congress": c, "bills": ";".join(bills)})
    pd.DataFrame(rows).to_csv(PROC / "ra_origin_bills.csv", index=False)
    print(f"{len(rows)} Republic Acts linked to the bills they came from")


def main(path):
    df = pd.read_parquet(path)
    print("columns:", list(df.columns))
    cols = {k: pick(df.columns, rx) for k, rx in WANT.items()}
    print("mapped:", cols)
    out = pd.DataFrame({k: df[c].map(flat) if c else "" for k, c in cols.items()})
    if not cols["number"]:
        src = df[pick(df.columns, r"basename|path|id")].astype(str) if pick(df.columns, r"basename|path|id") else out["title"]
        out["number"] = src.str.extract(r"(\d{3,5})", expand=False).fillna("")
    out["number"] = out["number"].astype(str).str.extract(r"(\d+)", expand=False).fillna("")
    out = out[out["number"] != ""].copy()
    out.insert(0, "id", "RA-" + out["number"])
    out = out.drop_duplicates("id")
    PROC.mkdir(parents=True, exist_ok=True)
    out.to_csv(PROC / "ra_summaries.csv.gz", index=False, compression="gzip")
    if "content" in df.columns:
        write_origins(df)
    li_p = PROC / "law_index.csv.gz"
    if li_p.exists():
        li = pd.read_csv(li_p, dtype=str).fillna("")
        new = out[~out["id"].isin(li["id"])][["id", "title"]]
        if len(new):
            pd.concat([li, new], ignore_index=True).to_csv(li_p, index=False, compression="gzip")
        print(f"{len(out)} Republic Acts; {len(new)} added to the law index")
    else:
        print(f"{len(out)} Republic Acts")


if __name__ == "__main__":
    main(sys.argv[1])
