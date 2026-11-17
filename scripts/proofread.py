"""Flag possible spelling and grammatical errors in bill titles and full texts (no AI, no dictionary download).

How it works
- Vocabulary: word counts from every full text read from a PDF (not OCR) and every title in the bill list.
- Spelling: a lower-case word that is rare (seen in at most 2 documents) and one letter away from a common word
  (seen in at least 40 documents and 25 times more often) is flagged, with the common word as the suggestion.
- Grammar and drafting checks: a repeated word ("the the"), "a" before a vowel sound or "an" before a consonant,
  a number written in words that differs from the figure beside it ("twelve (13)"), section numbers that skip or repeat,
  and unbalanced parentheses in titles.
Texts recognized from scanned PDFs (OCR) are checked only for number mismatches and section numbering, because
scanning errors would swamp real typos.

Writes data/processed/proofread.csv (one row per finding) and prints a summary.
Run: python scripts/proofread.py
"""
import csv
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from pipeline import catalogue  # noqa: E402
from pipeline.compare import load  # noqa: E402

OUT = ROOT / "data" / "processed" / "proofread.csv"
WORD = re.compile(r"[a-z]{4,}")
NUMS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen twenty".split())}
NUMS.update({"thirty": 30, "forty": 40, "fifty": 50, "sixty": 60, "seventy": 70, "eighty": 80, "ninety": 90, "hundred": 100})
AN_OK = re.compile(r"^(hour|honou?r|heir|herb)", re.I)          # "an" before a silent h
A_OK = re.compile(r"^(uni|use|usu|uti|eu|one|once|ubi|ura|uro)", re.I)  # "a" before a "you" or "won" sound
LETTERS = "abcdefghijklmnopqrstuvwxyz"


def edits1(w):
    splits = [(w[:i], w[i:]) for i in range(len(w) + 1)]
    return {a + b[1:] for a, b in splits if b} | {a + b[1] + b[0] + b[2:] for a, b in splits if len(b) > 1} | \
        {a + c + b[1:] for a, b in splits if b for c in LETTERS} | {a + c + b for a, b in splits for c in LETTERS}


NUMWORD = (r"(?:zero|one|two|three|four|five|six|seven|eight|nine|ten|eleven|twelve|thirteen|fourteen|fifteen|sixteen|seventeen|"
           r"eighteen|nineteen|twenty|thirty|forty|fifty|sixty|seventy|eighty|ninety|hundred|thousand|million|billion)")
PHRASE = re.compile(rf"(?<![A-Za-z-])\b({NUMWORD}(?:(?:[\s-]+|\s+and\s+){NUMWORD})*)\s*\((\d[\d,]*)\)", re.I)


def words_to_number(p):
    total, cur = 0, 0
    for w in re.split(r"[\s-]+", p.lower()):
        if w == "and":
            continue
        if w == "hundred":
            cur = max(cur, 1) * 100
        elif w in ("thousand", "million", "billion"):
            total += max(cur, 1) * {"thousand": 1000, "million": 10 ** 6, "billion": 10 ** 9}[w]
            cur = 0
        else:
            cur += NUMS.get(w, 0)
    return total + cur


def number_mismatch(t):
    t = re.sub(r"[\u2010-\u2015]", "-", t)
    out = []
    for m in PHRASE.finditer(t):
        val, fig = words_to_number(m.group(1)), int(m.group(2).replace(",", ""))
        if val != fig:
            out.append((m.group(0), f"{m.group(1)} ({val:,})"))
    return out


def article(t, common=()):
    out = []
    for m in re.finditer(r"\b(a|an) ([a-z]{3,})\b", t):
        art, nxt = m.group(1), m.group(2)
        if common and nxt not in common:
            continue
        if art == "a" and nxt[0].lower() in "aeio" and not A_OK.match(nxt):
            out.append((m.group(0), f"an {nxt}"))
        elif art == "an" and nxt[0].lower() not in "aeiou" and not AN_OK.match(nxt):
            out.append((m.group(0), f"a {nxt}"))
    return out


def doubled(t, common=()):
    return [(m.group(0), m.group(1)) for m in re.finditer(r"\b([A-Za-z]{3,}) \1\b", t)
            if m.group(1).lower() not in ("that", "had", "xxx") and (not common or m.group(1).lower() in common)]


def context(t, s, n=60):
    k = t.find(s)
    return " ".join(t[max(0, k - n):k + len(s) + n].split()) if k >= 0 else ""


def main():
    bills, secs = load()
    rows = catalogue.build()
    # vocabulary: in how many documents each word appears, and how often
    df, tf = Counter(), Counter()
    clean = [b for b, x in bills.items() if x.get("text_source") == "pdf_text"]
    for bid in clean:
        words = Counter(w for s_ in secs.get(bid, []) for w in WORD.findall(s_["text"]))
        df.update(words.keys())
        tf.update(words)
    for r in rows:
        ws = WORD.findall((r.get("title") or "").lower())
        df.update(set(ws))
        tf.update(ws)
    common = {w for w, n in df.items() if n >= 40}

    OCR_PAIRS = [("i", "l"), ("l", "i"), ("e", "c"), ("c", "e"), ("n", "u"), ("u", "n"), ("rn", "m"), ("m", "rn"), ("cl", "d"), ("li", "h")]

    def kind_of_edit(w, c):
        if len(w) == len(c):
            if sorted(w) == sorted(c):
                return "transpose"
            return "substitute"
        return "insert/delete"

    def suggest(w, strict):
        """A common word one edit away. In full texts only insertions, deletions and swaps of letters count, since a
        swapped-in letter is usually a scanning error or a different real word (sail/said)."""
        if len(w) < 6 or df[w] > (1 if strict else 2) or w in common:
            return None
        best = max((c for c in edits1(w) if c in common), key=lambda c: tf[c], default=None)
        if not best or tf[best] < 25 * max(tf[w], 1) or best.rstrip("s") == w.rstrip("s") or best.rstrip("d") == w.rstrip("d"):
            return None
        if strict and kind_of_edit(w, best) == "substitute":
            return None
        if best.startswith(w) or w.startswith(best) or best.endswith(w) or w.endswith(best):
            return None                          # a word cut in two by the PDF's text layer, not a typo
        if w.replace("re", "er") == best or w.replace("our", "or") == best:
            return None                          # British spelling
        if any(w.replace(a_, b_, 1) == best for a_, b_ in OCR_PAIRS):
            return None
        return best

    found = []

    def add(bid, where, kind, text, fix, ctx):
        found.append({"id": bid, "label": (bills.get(bid) or {}).get("label") or bid, "where": where, "type": kind,
                      "found": text, "suggestion": fix, "context": ctx})

    # titles
    for r in rows:
        t = r.get("title") or ""
        if not t:
            continue
        low = t.lower()
        for w in set(WORD.findall(low)):
            fix = suggest(w, False)
            if fix:
                add(r["id"], "Title", "Possible misspelling", w.upper(), fix.upper(), context(low, w).upper())
        for a, fix in doubled(t, common):
            add(r["id"], "Title", "Repeated word", a, fix, context(t, a))
        for a, fix in number_mismatch(t):
            add(r["id"], "Title", "Number in words differs from figure", a, fix, context(t, a))
        if t.count("(") != t.count(")"):
            add(r["id"], "Title", "Unbalanced parentheses", t.count("(") * "(" + t.count(")") * ")", "check the title", t[:160])

    # full texts
    for bid, b in bills.items():
        if b.get("kind") not in ("bill", "substitute"):
            continue
        ss = secs.get(bid, [])
        ocr = b.get("text_source") == "ocr"
        nos = [int(re.sub(r"\D", "", str(s_["no"])) or 0) for s_ in ss]
        for i in range(1, len(nos) if not ocr else 0):
            if nos[i] == nos[i - 1]:
                add(bid, f"Section {nos[i]}", "Section number repeated", f"Section {nos[i]}", f"Section {nos[i] + 1}?", ss[i]["heading"])
            elif nos[i] == nos[i - 1] + 2:
                add(bid, f"Section {nos[i]}", "Section number skipped (or not read)", f"Section {nos[i - 1]} then {nos[i]}",
                    f"Section {nos[i - 1] + 1}", ss[i]["heading"])
        for s_ in ss:
            t = s_["text"]
            where = f"Section {s_['no']} ({s_['heading']})"
            for a, fix in number_mismatch(t):
                add(bid, where, "Number in words differs from figure", a, fix, context(t, a))
            if ocr:
                continue
            for a, fix in doubled(t, common):
                add(bid, where, "Repeated word", a, fix, context(t, a))
            for a, fix in article(t, common):
                add(bid, where, "Article (a/an)", a, fix, context(t, a))
            for w in set(WORD.findall(t)):
                fix = suggest(w, True)
                if fix and re.search(rf"\b{w}\b", t) and "http" not in context(t, w):
                    add(bid, where, "Possible misspelling", w, fix, context(t, w))

    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", newline="") as f:
        wr = csv.DictWriter(f, fieldnames=["id", "label", "where", "type", "found", "suggestion", "context"])
        wr.writeheader()
        wr.writerows(found)
    c = Counter((x["where"] == "Title", x["type"]) for x in found)
    print(f"{len(found)} findings in {len({x['id'] for x in found})} documents -> {OUT.relative_to(ROOT)}")
    for (title, k), n in sorted(c.items()):
        print(f"  {'title' if title else 'text '}  {k}: {n}")


if __name__ == "__main__":
    main()
