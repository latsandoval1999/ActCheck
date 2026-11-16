"""Republic Acts with summaries from the BetterGov.PH Philippine Legal Documents Library (dataset 24;
huggingface.co/datasets/bettergovph/gov-library, CC BY-NC 4.0, from Lawphil.net, Arellano Law Foundation).

Writes data/processed/ra_summaries.csv.gz (one row per Republic Act: number, title, date, origin bill, purpose,
summary, laws affected) and adds any Republic Act missing from data/processed/law_index.csv.gz, so TrAIce can
find existing laws a bill touches and the bills that became law.

    python -m pipeline.ra_library <repacts_with_summary.parquet>
"""
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
