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


ORDINAL = {"sixteenth": 16, "seventeenth": 17, "eighteenth": 18, "nineteenth": 19, "twentieth": 20}


def passage(text):
    """Everything the text of a Republic Act says about where it came from: bill numbers if stated, the chamber it
    originated in, the Congress, dates, and the long title (for matching when no bill number is given)."""
    t = (text or "").replace("\xa0", " ")
    bills, c, passed, approved = origin_bills(t)
    m = re.search(r"\b(Sixteenth|Seventeenth|Eighteenth|Nineteenth|Twentieth)\s+Congress", t[:400], re.I)
    if m:
        c = ORDINAL[m.group(1).lower()]
        bills = [re.sub(r"-\d+-", f"-{c}-", b) for b in bills]
    o = re.search(r"originated\s+in\s+the\s+(House|Senate)", t)
    lt = re.search(r"\*{0,2}\s*(AN\s+ACT\b[^*\n]{10,1500})", t[:4000], re.I)
    return {"bills": bills, "congress": c, "passed": passed, "approved": approved,
            "chamber": ("HB" if o.group(1) == "House" else "SB") if o else "",
            "long_title": " ".join(lt.group(1).split()) if lt else ""}


def _norm(s):
    s = re.sub(r"[^A-Z0-9 ]", " ", (s or "").upper())
    s = re.sub(r"^\s*AN ACT\b", " ", s)
    return " ".join(s.split())


def match_titles(rows, catalogue_rows, threshold=0.82, margin=0.04):
    """For laws whose closing note names no bill ("This Act which originated in the House of Representatives was
    passed ..."), find the bill of that chamber and Congress with the same long title. A match needs a high
    similarity and a clear lead over the next candidate, so near-identical local bills are not confused."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from collections import defaultdict
    pools = defaultdict(list)
    for b in catalogue_rows:
        if b.get("title"):
            pools[("HB" if b["chamber"] == "House" else "SB", str(b["congress"]))].append(b)
    hits = 0
    by_pool = defaultdict(list)
    for r in rows:
        if not r["bills"] and r["long_title"] and r["congress"]:
            chambers = [r["chamber"]] if r["chamber"] else ["HB", "SB"]
            for ch in chambers:
                by_pool[(ch, str(r["congress"]))].append(r)
    for key, rs in by_pool.items():
        pool = pools.get(key)
        if not pool:
            continue
        vec = TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True).fit([_norm(b["title"]) for b in pool] + [_norm(r["long_title"]) for r in rs])
        P = vec.transform([_norm(b["title"]) for b in pool])
        Q = vec.transform([_norm(r["long_title"]) for r in rs])
        sims = (Q @ P.T).toarray()
        for r, row in zip(rs, sims):
            if r["bills"]:
                continue
            order = row.argsort()[::-1][:2]
            best = row[order[0]]
            second = row[order[1]] if len(order) > 1 else 0
            if best >= threshold and best - second >= margin:
                r["bills"] = [pool[order[0]]["id"]]
                r["basis"] = f"title match ({best:.2f})"
                hits += 1
    return hits


def write_origins(items):
    """items: (RA number, text). Writes data/processed/ra_origin_bills.csv: Republic Act -> the bills it came from."""
    rows = []
    for n, text in items:
        p = passage(text)
        if p["congress"]:
            rows.append({"ra": int(n), **p, "basis": "bill number in the Act" if p["bills"] else ""})
    try:
        from pipeline import catalogue
        matched = match_titles(rows, catalogue.build())
    except Exception as e:                      # matching is a bonus; the numbered links still save
        print("title matching skipped:", e)
        matched = 0
    out = [{"ra": r["ra"], "approved": r["approved"].isoformat() if r["approved"] else "", "passed": r["passed"].isoformat() if r["passed"] else "",
            "congress": r["congress"], "bills": ";".join(r["bills"]), "basis": r["basis"]} for r in rows if r["bills"]]
    pd.DataFrame(out).to_csv(PROC / "ra_origin_bills.csv", index=False)
    print(f"{len(out)} Republic Acts linked to the bills they came from ({matched} by title)")
    return out


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
        num = pick(df.columns, WANT["number"])
        write_origins((re.search(r"\d+", str(r[num])).group(), r["content"]) for _, r in df.iterrows()
                      if num and re.search(r"\d+", str(r[num])))
    li_p = PROC / "law_index.csv.gz"
    if li_p.exists():
        li = pd.read_csv(li_p, dtype=str).fillna("")
        new = out[~out["id"].isin(li["id"])][["id", "title"]]
        if len(new):
            pd.concat([li, new], ignore_index=True).to_csv(li_p, index=False, compression="gzip")
        print(f"{len(out)} Republic Acts; {len(new)} added to the law index")
    else:
        print(f"{len(out)} Republic Acts")


def main_md(folder):
    """Same links from a folder of Republic Act Markdown files (ra_<number>_<year>.md), e.g. a local copy of the library."""
    items = []
    for f in sorted(Path(folder).rglob("ra_*.md")):
        m = re.match(r"ra_(\d+)_\d{4}\.md$", f.name)
        if m:
            items.append((m.group(1), f.read_text(errors="ignore")))
    write_origins(items)


if __name__ == "__main__":
    if sys.argv[1] == "--md":
        main_md(sys.argv[2])
    else:
        main(sys.argv[1])
