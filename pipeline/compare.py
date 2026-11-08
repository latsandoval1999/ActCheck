"""Non-AI baseline: find related bills and align their sections.

This is the comparator for the AI agents (the "keyword search + manual reading"
benchmark in the A2 design) and the anchor that agent outputs are checked
against. It uses TF-IDF cosine similarity only, so results are reproducible.
"""
import json
import re
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path

from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"

SAME, CHANGED = 0.85, 0.45  # text-similarity thresholds; tune on 19th Congress pairs, test on 20th
HEADING_MATCH, HEADING_MIN_TEXT = 0.75, 0.10  # same heading + some shared text = same provision, rewritten


def _norm_heading(h):
    h = re.sub(r"\b(the|of|and|a|an)\b", " ", h.lower())
    return re.sub(r"[^a-z ]", "", re.sub(r"\s+", " ", h)).strip()


def heading_sim(x, y):
    return SequenceMatcher(None, _norm_heading(x), _norm_heading(y)).ratio()


@lru_cache(maxsize=1)
def load():
    bills = {}
    for line in open(PROC / "bills.jsonl"):
        b = json.loads(line)
        bills[b["id"]] = b
    secs = {}
    for line in open(PROC / "sections.jsonl"):
        s = json.loads(line)
        secs.setdefault(s["bill"], []).append(s)
    return bills, secs


@lru_cache(maxsize=1)
def section_vectorizer():
    """One TF-IDF model fitted on every section in the corpus (global IDF)."""
    _, secs = load()
    texts = [x["heading"] + " " + x["text"] for v in secs.values() for x in v]
    return TfidfVectorizer(ngram_range=(1, 2), sublinear_tf=True, min_df=1).fit(texts)


def bill_text(bid):
    _, secs = load()
    return " ".join(s["text"] for s in secs.get(bid, []))


def related_bills(bid, top=10, include_laws=False):
    """Rank other documents by whole-text similarity to bill `bid`."""
    bills, _ = load()
    ids = [i for i, b in bills.items() if i != bid and (include_laws or not b["is_law"])]
    docs = [bill_text(bid)] + [bill_text(i) for i in ids]
    vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=1, sublinear_tf=True)
    m = vec.fit_transform(docs)
    sims = cosine_similarity(m[0:1], m[1:]).ravel()
    ranked = sorted(zip(ids, sims), key=lambda x: -x[1])[:top]
    return [{"id": i, "label": bills[i]["label"], "congress": bills[i]["congress"], "family": bills[i]["family"],
             "title": bills[i]["title"], "similarity": round(float(s), 3)} for i, s in ranked]


def align(a, b):
    """Align each section of bill a to its best match in bill b.

    status: 'same' (near-identical), 'changed' (same provision, different wording
    or terms), 'new in A' (no counterpart in B). Sections of B with no match are
    returned as 'only in B'.
    """
    _, secs = load()
    sa, sb = secs.get(a, []), secs.get(b, [])
    if not sa or not sb:
        return []
    texts = [s["heading"] + " " + s["text"] for s in sa + sb]
    m = section_vectorizer().transform(texts)
    sim = cosine_similarity(m[: len(sa)], m[len(sa):])
    rows, used = [], set()
    for i, s in enumerate(sa):
        hs = [heading_sim(s["heading"], t["heading"]) for t in sb]
        combo = [0.7 * float(sim[i, k]) + 0.3 * hs[k] for k in range(len(sb))]
        j = max(range(len(sb)), key=lambda k: combo[k])
        score = float(sim[i, j])
        if score >= SAME:
            status = "same"
        elif score >= CHANGED or (hs[j] >= HEADING_MATCH and score >= HEADING_MIN_TEXT):
            status = "changed"
        else:
            status = "new in A"
        if status != "new in A":
            used.add(j)
        rows.append({"a_section": s["id"], "a_no": s["no"], "a_heading": s["heading"],
                     "b_section": sb[j]["id"] if status != "new in A" else "", "b_no": sb[j]["no"] if status != "new in A" else None,
                     "b_heading": sb[j]["heading"] if status != "new in A" else "", "similarity": round(score, 3), "status": status})
    for j, s in enumerate(sb):
        if j not in used:
            rows.append({"a_section": "", "a_no": None, "a_heading": "", "b_section": s["id"], "b_no": s["no"],
                         "b_heading": s["heading"], "similarity": None, "status": "only in B"})
    return rows


def summary(rows):
    out = {"same": 0, "changed": 0, "new in A": 0, "only in B": 0}
    for r in rows:
        out[r["status"]] += 1
    n = out["same"] + out["changed"] + out["new in A"]
    out["share_same"] = round(out["same"] / n, 2) if n else 0
    return out
