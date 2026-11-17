"""Filing dates read from the House receiving stamp ("RECEIVED  DATE 09 NOV 2026", upper right of page 1).

For every House bill on the Bills page that has no filing date, and for dates that look wrong (out of order with the
bills numbered just before and after it), this step reads the stamp:
  1. from the text ActCheck already has, looking only near the stamp words (RECEIVED, DATE, TIME, BY);
  2. if that fails, by downloading page 1 of the bill PDF from the House documents server and reading the top of
     the page again with OCR, at high resolution, in several image variants (stamps are often faint or coloured).
A date is accepted when it is read in full and fits the filing order (House bill numbers are given in the order
bills are received, so a bill's date lies between the dates of the bills numbered just before and after it).
When a digit is smudged but the rest of the stamp is readable and the filing order leaves only one possible date,
that date is accepted and labelled as such. Otherwise the bill is marked "date not clearly visible; verify in file",
and the image of the stamp area is saved for a person to check.

    python -m pipeline.stamp_dates [--limit 800] [--minutes 150] [--crops DIR]
        -> data/processed/stamp_dates.csv  (id, date_filed, basis, read)
"""
import argparse
import csv
import itertools
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.request
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw_text"
OUT = ROOT / "data" / "processed" / "stamp_dates.csv"
HOUSE_PDF = "https://docs.congress.hrep.online/legisdocs/basic_{c}/HB{n:05d}.pdf"
CONGRESS_DATES = {18: (date(2019, 7, 1), date(2022, 6, 30)), 19: (date(2022, 7, 1), date(2025, 6, 30)),
                  20: (date(2025, 7, 1), date(2028, 6, 30))}
MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
UNCLEAR = "date not clearly visible; verify in file"
SLACK = timedelta(days=2)

# characters OCR often reads in place of digits on rubber stamps
DIGIT = {"O": "0", "o": "0", "Q": "0", "D": "0", "U": "0", "l": "1", "I": "1", "|": "1", "i": "1", "!": "1", "]": "1",
         "[": "1", "J": "1", "Z": "2", "z": "2", "S": "5", "s": "5", "$": "5", "B": "8", "g": "9", "q": "9"}
WILD = set("%§&@#?*~^")
LET = {"0": "O", "1": "I", "5": "S", "8": "B", "2": "Z", "4": "A", "6": "G", "|": "I", "!": "I"}


def _digits(tok):
    """'0 9' -> '09'; 'O9' -> '09'; '9%' -> '9?' (? = unreadable)."""
    out = ""
    for ch in tok:
        if ch.isdigit():
            out += ch
        elif ch in DIGIT:
            out += DIGIT[ch]
        elif ch in WILD:
            out += "?"
        elif ch.isspace():
            continue
        else:
            return None
    return out


TWO = {}
for _i, _m in enumerate(MONTHS):
    for _k in (_m[:2], _m[1:]):
        TWO.setdefault(_k, set()).add(_i + 1)


def _month(tok):
    """(month, exact) or (None, False). Exact = the three letters read as printed."""
    t = "".join(LET.get(c, c) for c in tok.upper() if c.isalnum())[:3]
    if t in MONTHS:
        return MONTHS.index(t) + 1, True
    if len(t) == 3:
        near = [i for i, m in enumerate(MONTHS) if sum(a != b for a, b in zip(t, m)) == 1]
        if len(near) == 1:
            return near[0] + 1, False
    if len(t) == 2 and len(TWO.get(t, ())) == 1:          # 'CT' for OCT: a letter lost
        return next(iter(TWO[t])), False
    return None, False


STAMP = re.compile(r"(?<![A-Za-z0-9])([0-9OoQDUlI|i!\]\[JZzSs$Bgq%§&@#?*]{1,2}(?:\s[0-9OoQDlI|Zz%§?](?=\s))?)\s*[-./,]?\s*"
                   r"([A-Za-z0-9|!]{2,3})[A-Za-z.]{0,6}\s*[-./,]?\s*"
                   r"([2Z][0-9OoQDlI|Zz%§?]\s?[0-9OoQDlI|Zz%§?]\s?[0-9OoQDlI|Zz%§?S$B&]?)(?![0-9])")


FULL = ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE", "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"]
LONG = re.compile(r"(" + "|".join(FULL) + r")\s*[.,]?\s*([0-9OoQDlI|Zz%§?]{1,2})\s*[,.]?\s*([2Z][0-9OoQDlI|Zz%§?]{2,3})(?![0-9])", re.I)


def _iter(text):
    """(day, month token, year) triples in 'DD MON YYYY' and 'Month DD, YYYY' order."""
    for m in STAMP.finditer(text):
        yield m.group(1), m.group(2), m.group(3), m.group(0)
    for m in LONG.finditer(text):
        yield m.group(2), m.group(1)[:3], m.group(3), m.group(0)


LOOSE = re.compile(r"(?:DATE|PATE|DATED|PARE|DAT|OATE)[\W_]{0,4}([0-9OoIl|SsZB%§?]{1,2})(?:[\W_]{0,3}([A-Za-z0-9|()]{2,4}))?"
                   r"(?:[\W_]{0,3}([0-9OoIl|Zz%§?]{2,4}))?", re.I)


def loose(text, congress):
    """Fallback for smudged stamps: the day after the word DATE, with whatever of the month and year can be read.
    Every reading is partial (quality 0), so it is only accepted when the filing order leaves a single date."""
    lo, hi = CONGRESS_DATES.get(congress, (date(2000, 1, 1), date(2100, 1, 1)))
    out = []
    for m in LOOSE.finditer(text):
        d = _digits(m.group(1))
        if not d or "?" in d or not (1 <= int(d) <= 31):
            continue
        mo_tok = (m.group(2) or "").upper()
        mo, _ = _month(mo_tok) if mo_tok else (None, False)
        months = [mo] if mo else sorted({i + 1 for i, x in enumerate(MONTHS) if mo_tok[:2] and x.startswith(mo_tok[:2])}) or list(range(1, 13))
        y = _digits(m.group(3) or "") or ""
        years = [int(y)] if len(y) == 4 and "?" not in y and lo.year <= int(y) <= hi.year else list(range(lo.year, hi.year + 1))
        for mm in months:
            for yy in years:
                try:
                    dt = date(yy, mm, int(d))
                except ValueError:
                    continue
                if lo <= dt <= hi:
                    out.append((dt, -1, m.group(0)))       # day read; month or year completed from the order
    return out


def candidates(text, congress):
    """Every (date, quality, raw) the text could mean. quality 2 = read exactly; 1 = one letter or digit of the
    month or year misread (e.g. 'CT' for OCT, '2075' for 2025); 0 = a smudged digit, filled with every value that
    makes a real date inside the Congress."""
    lo, hi = CONGRESS_DATES.get(congress, (date(2000, 1, 1), date(2100, 1, 1)))
    out = []
    for g1, g2, g3, raw in _iter(text):
        d, (mo, mexact), y = _digits(g1), _month(g2), _digits(g3)
        if not (d and mo and y) or len(d) > 2 or not (3 <= len(y) <= 4):
            continue
        q = 2 if mexact else 1
        years = [y]
        if len(y) == 3:                                     # '205' or '20%': one digit lost
            years = sorted({y[:i] + k + y[i:] for i in range(4) for k in "0123456789"} if "?" not in y else
                           {y.replace("?", "") [:i] + k + y.replace("?", "")[i:] for i in range(3) for k in "0123456789"})
            years, q = [v for v in years if "?" not in v and lo.year <= int(v) <= hi.year], 0
        elif "?" in y:
            years, q = ["".join(p) for p in itertools.product(*[[c] if c != "?" else list("0123456789") for c in y])], 0
        elif not (lo.year <= int(y) <= hi.year):            # one digit of the year misread
            years = [str(v) for v in range(lo.year, hi.year + 1) if sum(a != b for a, b in zip(str(v), y)) == 1]
            q = min(q, 1)
        days = [d]
        if "?" not in d and len(d) == 2 and int(d) > 31:   # '86' for '06': first digit misread
            d = "?" + d[1]
        if "?" in d:
            days, q = [d.replace("?", str(k), 1) for k in range(10)] + ([d.replace("?", "")] if len(d) == 2 else []), 0
        for dd, yy in itertools.product(days, years):
            try:
                dt = date(int(yy), mo, int(dd))
            except ValueError:
                continue
            if lo <= dt <= hi:
                out.append((dt, q, raw))
    return out


def stamp_zone(text):
    """The part of the first page where the receiving stamp's words appear (the stamp is read before or around
    the 'HOUSE BILL NO.' line; dates in the bill's own text are ignored)."""
    head = text[:2500]
    zones = []
    for m in re.finditer(r"RECEIVED|DATE|TIME|BY\b|BILLS\s+AND\s+INDEX|INDEX\s+SERVICE", head, re.I):
        zones.append(head[max(0, m.start() - 40): m.end() + 80])
    cut = re.search(r"AN\s+ACT|EXPLANATORY\s+NOTE", head)
    zones.append(head[: cut.start() if cut else 900])
    return "\n".join(zones)


def decide(cands, lo, hi):
    """lo/hi: dates of the nearest bills numbered before and after (None if unknown)."""
    fits = lambda dt: (lo is None or dt >= lo - SLACK) and (hi is None or dt <= hi + SLACK)
    from collections import Counter
    for q in (2, 1):
        votes = Counter(dt for dt, qq, _ in cands if qq == q and fits(dt))
        if len(votes) == 1:
            return next(iter(votes)), "receiving stamp"
        if len(votes) > 1:                                   # several image versions disagree: a clear majority wins
            (top, n1), (_, n2) = votes.most_common(2)
            if n1 >= 2 * n2 and n1 >= 2:
                return top, "receiving stamp"
            return None, ""                                  # otherwise leave it to a person
    partial = {dt for dt, qq, _ in cands if qq == 0 and lo and hi and lo <= dt <= hi}
    if not partial:                                          # only the day was legible: allow one day either side
        one = timedelta(days=1)
        partial = {dt for dt, qq, _ in cands if qq == -1 and lo and hi and lo - one <= dt <= hi + one}
    if len(partial) == 1 and lo and hi:
        return next(iter(partial)), "receiving stamp, partly legible; completed from the filing order"
    return None, ""


# ---------------------------------------------------------------- OCR of page 1
def fetch(url):
    req = urllib.request.Request(url, headers={"User-Agent": "ActCheck student research prototype (PP5538, NUS)"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return r.read()


def ocr_page1(pdf_bytes, save_crop=None):
    from PIL import Image, ImageOps
    texts = []
    with tempfile.TemporaryDirectory() as tmp:
        p = Path(tmp) / "b.pdf"
        p.write_bytes(pdf_bytes)
        subprocess.run(["pdftoppm", "-f", "1", "-l", "1", "-r", "300", "-png", str(p), str(Path(tmp) / "pg")],
                       check=True, capture_output=True, timeout=120)
        png = sorted(Path(tmp).glob("pg*.png"))[0]
        im = Image.open(png).convert("RGB")
        w, h = im.size
        top = im.crop((0, 0, w, int(h * 0.42)))
        right = im.crop((int(w * 0.45), 0, w, int(h * 0.32)))
        if save_crop:
            top.convert("L").resize((int(top.width * 0.4), int(top.height * 0.4))).save(save_crop)
        variants = []
        for region in (right, top):
            g = ImageOps.autocontrast(region.convert("L"))
            red = ImageOps.autocontrast(region.split()[0])  # blue or violet ink turns dark in the red channel
            variants += [g, red.point(lambda v: 255 if v > 150 else 0), g.resize((g.width * 3 // 2, g.height * 3 // 2))]
        for i, v in enumerate(variants):
            f = Path(tmp) / f"v{i}.png"
            v.save(f)
            for psm in ("11", "6"):
                r = subprocess.run(["tesseract", str(f), "-", "--psm", psm], capture_output=True, text=True, timeout=120)
                texts.append(r.stdout)
                yield r.stdout


# ---------------------------------------------------------------- which bills, and their neighbours
def parse(d):
    try:
        return datetime.strptime(d, "%B %d, %Y").date()
    except Exception:
        return None


def nice(dt):
    return f"{dt.strftime('%B')} {dt.day}, {dt.year}"


def load_text(c, n):
    for f in (RAW / f"{c}th Congress").rglob(f"HB{n:05d}.txt") if (RAW / f"{c}th Congress").exists() else []:
        return f.read_text(errors="ignore")
    for f in RAW.rglob(f"HB{n:05d}.txt"):
        if f"{c}th Congress" in str(f):
            return f.read_text(errors="ignore")
    return ""


def _neighbours(points):
    """points: sorted [(number, date)] -> function(number) -> (date before, date after)."""
    import bisect
    nums = [p[0] for p in points]

    def nb(n):
        i = bisect.bisect_left(nums, n)
        lo = points[i - 1][1] if i > 0 else None
        j = i + 1 if i < len(nums) and nums[i] == n else i
        return lo, (points[j][1] if j < len(nums) else None)
    return nb


def targets(rows, prior, retry=False):
    """[(row, must_download)] for House bills whose date was not taken from Open Congress Data:
    no date yet (download if the text has no readable stamp), or a date read earlier from the PDF text (re-read
    near the stamp words; download only if it is out of filing order). Returns also each bill's date bounds."""
    by_c = {}
    for r in rows:
        if r["chamber"] == "House":
            by_c.setdefault(int(r["congress"]), []).append(r)
    todo, bounds = [], {}
    for c, rs in by_c.items():
        rs.sort(key=lambda r: r["number"])
        trusted = _neighbours([(r["number"], parse(r["date_filed"])) for r in rs if parse(r["date_filed"])
                               and (r["date_basis"] != "page 1 of the bill PDF" or "receiving stamp" in prior.get(r["id"], {}).get("basis", ""))])
        bad = set()
        for r in rs:
            d = parse(r["date_filed"])
            if d and r["date_basis"] == "page 1 of the bill PDF":
                tlo, thi = trusted(r["number"])
                if (tlo and d < tlo - SLACK) or (thi and d > thi + SLACK) or d > date.today():
                    bad.add(r["id"])
        dated = _neighbours([(r["number"], parse(r["date_filed"])) for r in rs if parse(r["date_filed"]) and r["id"] not in bad])
        for r in rs:
            lo, hi = dated(r["number"])
            if hi is None and c == 20:
                hi = date.today()
            bounds[r["id"]] = (lo, hi)
            if parse(r["date_filed"]) and r["date_basis"] != "page 1 of the bill PDF":
                continue                                    # date from the bill list (Open Congress Data, House or Senate)
            pb = prior.get(r["id"], {}).get("basis", "")
            if pb and not (retry and pb == UNCLEAR):
                continue                                    # decided in an earlier run
            todo.append((r, not parse(r["date_filed"]) or r["id"] in bad))
    return todo, bounds


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int, default=800)
    ap.add_argument("--minutes", type=float, default=float(os.environ.get("STAMP_MINUTES", "150")))
    ap.add_argument("--crops", default="", help="folder for images of stamps that could not be read")
    ap.add_argument("--no-download", action="store_true")
    ap.add_argument("--retry", action="store_true", help="try again the bills marked unclear in earlier runs")
    a = ap.parse_args()
    sys.path.insert(0, str(ROOT))
    from pipeline import catalogue
    prior = {}
    if OUT.exists():
        with open(OUT, newline="", encoding="utf-8") as f:
            prior = {r["id"]: r for r in csv.DictReader(f)}
    rows = catalogue.build(stamps=False)
    todo, bounds = targets(rows, prior, a.retry)
    print(f"{len(todo)} House bills to check; {sum(1 for _, m in todo if m)} without a date or with a date out of filing order")
    start, done = time.time(), dict(prior)
    stats = {"text": 0, "ocr": 0, "partial": 0, "unclear": 0, "skipped": 0}
    for k, (r, must) in enumerate(todo):
        if (time.time() - start) / 60 > a.minutes:
            stats["skipped"] = len(todo) - k
            break
        c, n = int(r["congress"]), r["number"]
        lo, hi = bounds.get(r["id"], (None, None))
        text = load_text(c, n)
        z = stamp_zone(text) if text else ""
        dt, basis = decide(candidates(z, c) + loose(z, c), lo, hi) if text else (None, "")
        how = "text"
        if not dt and not must:
            continue                                        # the date already shown fits the filing order
        tried = False
        if not dt:
            if a.no_download or stats["ocr"] + stats["partial"] + stats["unclear"] >= a.limit:
                continue                                    # not checked this run; stays for the next one
            url = r.get("source_url") or HOUSE_PDF.format(c=c, n=n)
            if "hrep.online" not in url:
                url = HOUSE_PDF.format(c=c, n=n)
            try:
                pdf = fetch(url)
                tried = True
                time.sleep(1.5)
                crop = Path(a.crops) / f"{r['id']}.png" if a.crops else None
                if crop:
                    crop.parent.mkdir(parents=True, exist_ok=True)
                cands = []
                for t in ocr_page1(pdf, crop):
                    cands += candidates(t, c) + loose(t, c)
                    if os.environ.get("STAMP_DEBUG"):
                        hits = [ln for ln in t.splitlines() if re.search(r"DATE|RECEIV|NOV|OCT|SEP|AUG|DEC|JAN|FEB|MAR|20[0-9%]{2}", ln, re.I)]
                        print(f"    {r['label']} ocr: {' | '.join(hits)[:300]}")
                    dt, basis = decide(cands, lo, hi)
                    if dt and basis == "receiving stamp":
                        break                               # a clean reading is enough
                how = "ocr"
                if dt and crop and crop.exists():
                    crop.unlink()
            except Exception as e:
                print(f"  {r['label']}: PDF not read ({type(e).__name__})")
            if not tried:
                continue
        if dt:
            stats["partial" if "partly" in basis else how] += 1
            done[r["id"]] = {"id": r["id"], "date_filed": nice(dt), "basis": basis + (" (OCR of page 1)" if how == "ocr" else "")}
        else:
            stats["unclear"] += 1
            done[r["id"]] = {"id": r["id"], "date_filed": "", "basis": UNCLEAR}
        if k % 25 == 0:
            print(f"  {k + 1}/{len(todo)} {r['label']}: {done[r['id']]['date_filed'] or UNCLEAR}", flush=True)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["id", "date_filed", "basis"], extrasaction="ignore")
        w.writeheader()
        w.writerows(sorted(done.values(), key=lambda x: x["id"]))
    print("stamp dates:", stats)


if __name__ == "__main__":
    main()
