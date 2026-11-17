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

import numpy as np
from sklearn.feature_extraction.text import HashingVectorizer, TfidfTransformer, TfidfVectorizer  # noqa: F401
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


class Sections:
    """Read-only {bill id: [sections]} that keeps the 50 MB section file on disk. Only the position of each
    bill's lines is held in memory; a bill's sections are read when asked for (the last 48 are kept)."""

    def __init__(self, path):
        self.path = path
        self.where = {}                                   # bill -> [(offset, length)]
        with open(path, "rb") as f:
            pos = 0
            for line in f:
                m = re.search(rb'"bill":\s*"([^"]+)"', line[:400])
                if m:
                    self.where.setdefault(m.group(1).decode(), []).append((pos, len(line)))
                pos += len(line)

    @lru_cache(maxsize=48)
    def _read(self, bid):
        spans = self.where.get(bid)
        if not spans:
            return ()
        out = []
        with open(self.path, "rb") as f:
            start, end = spans[0][0], spans[-1][0] + spans[-1][1]
            if end - start == sum(n for _, n in spans):       # the bill's lines are together (as written)
                f.seek(start)
                out = [json.loads(x) for x in f.read(end - start).splitlines() if x.strip()]
            else:
                for o, n in spans:
                    f.seek(o)
                    out.append(json.loads(f.read(n)))
        return tuple(out)

    def get(self, bid, default=None):
        r = self._read(bid)
        return list(r) if r else ([] if default is None else default)

    def __getitem__(self, bid):
        if bid not in self.where:
            raise KeyError(bid)
        return self.get(bid)

    def __contains__(self, bid):
        return bid in self.where

    def __iter__(self):
        return iter(self.where)

    def __len__(self):
        return len(self.where)

    def keys(self):
        return self.where.keys()

    def values(self):
        """Streams every bill's sections from disk, in file order, without keeping them."""
        cur, buf = None, []
        with open(self.path, encoding="utf-8") as f:
            for line in f:
                s = json.loads(line)
                if s["bill"] != cur and buf:
                    yield buf
                    buf = []
                cur = s["bill"]
                buf.append(s)
        if buf:
            yield buf

    def items(self):
        for v in self.values():
            yield v[0]["bill"], v


@lru_cache(maxsize=1)
def load():
    bills = {}
    for line in open(PROC / "bills.jsonl"):
        b = json.loads(line)
        bills[b["id"]] = b
    return bills, Sections(PROC / "sections.jsonl")


# Memory: the hosting limit is about 1 GB and the corpus grows every day, so the similarity models use hashed
# features (no vocabulary kept in memory), float32 numbers, and are built once per process.
HASH_FEATURES = 2 ** 20
DOC_CHARS = 40_000


class _HashedTfidf:
    """TF-IDF (sublinear tf, smooth idf, l2 norm, as sklearn) on hashed unigrams and bigrams. The idf is learned
    in a stream, so fitting keeps only one number per feature in memory."""

    def __init__(self, stop_words=None):
        self.h = HashingVectorizer(ngram_range=(1, 2), n_features=HASH_FEATURES, alternate_sign=False, norm=None,
                                   stop_words=stop_words, dtype=np.float32)
        self.idf = None

    def _chunks(self, texts, size):
        buf = []
        for t in texts:
            buf.append(t)
            if len(buf) == size:
                yield self.h.transform(buf)
                buf = []
        if buf:
            yield self.h.transform(buf)

    def _weight(self, x):
        from sklearn.preprocessing import normalize
        x = x.tocsr().astype(np.float32)
        np.log(x.data, out=x.data)
        x.data += 1
        x.data *= self.idf[x.indices]                       # in place: no dense row is ever made
        return normalize(x, copy=False)

    def fit(self, texts, size=50):
        df, n = np.zeros(HASH_FEATURES, dtype=np.int64), 0
        for x in self._chunks(texts, size):
            df += np.bincount(x.indices, minlength=HASH_FEATURES)
            n += x.shape[0]
        self.idf = (np.log((1 + n) / (1 + df)) + 1).astype(np.float32)
        return self

    def transform(self, texts):
        return self.h.transform(texts) if self.idf is None else self._weight(self.h.transform(texts))

    def fit_transform(self, texts, size=4):
        """texts: a list, or a function that returns a fresh iterator (then the texts are read twice, once to
        learn the idf and once to weight them, and never all held in memory)."""
        from scipy.sparse import vstack
        if callable(texts):
            self.fit(texts(), size)
            return vstack([self._weight(p) for p in self._chunks(texts(), size)], format="csr")
        parts = list(self._chunks(texts, size))
        self.fit_counts(parts)
        return vstack([self._weight(p) for p in parts], format="csr")

    def fit_counts(self, parts):
        df, n = np.zeros(HASH_FEATURES, dtype=np.int64), 0
        for x in parts:
            df += np.bincount(x.indices, minlength=HASH_FEATURES)
            n += x.shape[0]
        self.idf = (np.log((1 + n) / (1 + df)) + 1).astype(np.float32)


@lru_cache(maxsize=1)
def section_vectorizer():
    """One TF-IDF model fitted on every section in the corpus (global IDF)."""
    _, secs = load()
    return _HashedTfidf().fit(x["heading"] + " " + x["text"] for v in secs.values() for x in v)


@lru_cache(maxsize=1)
def _doc_matrix():
    """Whole-text TF-IDF of every document, built once: (ids, matrix)."""
    bills, _ = load()
    ids = [i for i, b in bills.items() if b.get("kind") != "reference"]
    # the first 40,000 characters (title, policy, structure and main provisions) are enough to tell related bills
    # apart; longer texts only add memory
    m = _HashedTfidf(stop_words="english").fit_transform(lambda: (bill_text(i, cache=False)[:DOC_CHARS] for i in ids))
    import gc
    gc.collect()
    return ids, {i: k for k, i in enumerate(ids)}, m


def bill_text(bid, cache=True):
    _, secs = load()
    rows = secs.get(bid, []) if cache else secs._read.__wrapped__(secs, bid)
    return " ".join(s["text"] for s in rows)


def related_bills(bid, top=10, include_laws=False):
    """Rank other documents by whole-text similarity to bill `bid`."""
    bills, _ = load()
    ids, pos, m = _doc_matrix()
    if bid not in pos:
        return []
    sims = cosine_similarity(m[pos[bid]:pos[bid] + 1], m).ravel()
    keep = [(i, sims[k]) for k, i in enumerate(ids) if i != bid and (include_laws or not bills[i]["is_law"])]
    ranked = sorted(keep, key=lambda x: -x[1])[:top]
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
