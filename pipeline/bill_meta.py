"""Filing date and principal author read from the first page of each House bill PDF ActCheck has (the receiving
stamp, e.g. "RECEIVED DATE 09 NOV 2026", and the "Introduced by" line). Used when the bill list has no date or author.

    python -m pipeline.bill_meta      -> data/processed/bill_meta.csv
"""
import csv
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw_text"
OUT = ROOT / "data" / "processed" / "bill_meta.csv"
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
FULL = ["January", "February", "March", "April", "May", "June", "July", "August", "September", "October", "November", "December"]
HONORIFIC = r"(?:Hon(?:orable)?\.?|Rep(?:resentative)?\.?|Congress(?:man|woman)|Cong\.|Dr\.|Atty\.|Engr\.|Deputy Speaker|Majority Leader|Minority Leader|Speaker)"


CONGRESS_YEARS = {18: (2019, 2022), 19: (2022, 2025), 20: (2025, 2028)}


def filed_date(text, congress=None):
    """The first date on the first page that falls within the bill's Congress (the receiving stamp comes first)."""
    head = text[:1500]
    lo, hi = CONGRESS_YEARS.get(congress, (2000, 2100))
    found = []
    for m in re.finditer(r"\b(\d{1,2})\s*[-/ ]?\s*(" + "|".join(MONTHS) + r")[A-Z]*\.?\s*[-/ ]?\s*(20\d\d)\b", head, re.I):
        found.append((m.start(), int(m.group(3)), f"{FULL[MONTHS.index(m.group(2).upper()[:3])]} {int(m.group(1))}, {m.group(3)}"))
    for m in re.finditer(r"\b(" + "|".join(FULL) + r")\s+(\d{1,2}),?\s*(20\d\d)\b", head, re.I):
        found.append((m.start(), int(m.group(3)), f"{m.group(1).title()} {int(m.group(2))}, {m.group(3)}"))
    ok = sorted(x for x in found if lo <= x[1] <= hi)
    return ok[0][2] if ok else ""


def principal_author(text):
    head = " ".join(text[:3000].split())
    m = re.search(r"Introduced\s+by\s*:?\s*(.{3,200}?)(?=\s+(?:AN\s+ACT|EXPLANATORY\s+NOTE|AN\s+ACT|A\s+BILL)\b)", head, re.I)
    if not m:
        return ""
    s = m.group(1)
    s = re.split(r"\s+(?:House\s+Bill|[A-Za-z]+\s+District|Lone\s+District|Province\s+of|City\s+of)\b", s, flags=re.I)[0]
    parts = re.split(HONORIFIC, s, flags=re.I)           # the name follows the last honorific
    name = parts[-1] if len(parts) > 1 and len(parts[-1].strip()) > 3 else s
    name = re.split(r"\s+(?:and|AND|&)\s+|,\s*(?=[A-Z][a-z]+\s)|;|\s{2,}", name.strip(" :,."))[0]
    name = re.sub(r"\s*\(.*$", "", name).strip(" :,.")
    name = re.sub(r"\s*Party[- ]?list\b.*$", "", name, flags=re.I).strip(" :,.") or name
    if not re.search(r"[A-Za-z]{2}", name) or len(name) > 60:
        return ""
    name = re.sub(r"\s+(First|Second|Third|Fourth|Fifth|Sixth|Seventh|Eighth)$", "", name, flags=re.I).strip(" ,.")
    return name.title() if name.isupper() else name


def main():
    rows = []
    for f in sorted(RAW.rglob("HB*.txt")):
        m = re.match(r"HB0*(\d+)\.txt$", f.name)
        c = re.search(r"(\d{2})th Congress", str(f))
        if not (m and c):
            continue
        t = f.read_text(errors="ignore")
        d, a = filed_date(t, int(c.group(1))), principal_author(t)
        if d or a:
            rows.append({"id": f"HB-{c.group(1)}-{m.group(1)}", "date_filed": d, "author": a})
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=["id", "date_filed", "author"])
        w.writeheader()
        w.writerows(rows)
    print(f"{len(rows)} House bills: {sum(1 for r in rows if r['date_filed'])} dates, {sum(1 for r in rows if r['author'])} authors from the PDF")


if __name__ == "__main__":
    main()
