"""BILLy, the review companion: answers questions about the bill open in the review workspace.

* With an API key: the grounded chat in agents/chat.py (answers only from the bill's workspace, with
  checked citations).
* Without a key: search mode. It ranks the bill's own sections (and explanatory note) against the
  question and quotes the best matches with their section IDs. No AI, nothing invented.
"""
import re

from pipeline.compare import load


def suggestions(bid):
    bills, _ = load()
    b = bills.get(bid, {})
    qs = ["What does the bill create, and who heads it?", "How is it funded?", "Which existing laws does it amend or overlap with?"]
    f = b.get("facts") or {}
    if f.get("salary_grades"):
        qs.append("What salary grades does it set?")
    if b.get("congress") and b["congress"] != "18":
        qs.append("Was it filed in an earlier Congress?")
    qs.append("What are the main functions of the new body?")
    return qs[:5]


def _docs(bid):
    bills, secs = load()
    out = [(f"{bid}:s{s['no']}", f"Sec. {s['no']}. {s['heading']}", s["text"]) for s in secs.get(bid, [])]
    note = (bills.get(bid, {}).get("explanatory_note") or "").strip()
    if note:
        out.append((f"{bid}:note", "Explanatory note", note))
    return out


SYN = {"fund": "appropriations appropriated budget cost amount charged", "head": "chairperson director executive head secretary appointed",
       "salary": "salary grade rank", "overlap": "amend amending republic act law repeal", "function": "powers functions mandate",
       "earlier": "congress filed refiled", "create": "creation created established composition"}
STOP = set("the and for that this with shall from such any are its which will may into other have has been not all who what how does "
           "bill act section".split())


def _tokens(s):
    """Light stemming: the first six letters of each word, so 'appropriations' matches 'appropriated'."""
    return [w[:6] for w in re.findall(r"[a-z]{3,}", s.lower()) if w not in STOP]


def search(bid, question, k=3):
    """Return [(section_id, heading, excerpt, score)] from the bill's own text."""
    docs = _docs(bid)
    if not docs:
        return []
    from sklearn.feature_extraction.text import TfidfVectorizer
    q = question.lower()
    for key, extra in SYN.items():
        if key in q:
            q += " " + extra
    vec = TfidfVectorizer(analyzer=_tokens, sublinear_tf=True)
    m = vec.fit_transform([(h + " ") * 3 + t for _, h, t in docs] + [q])
    scores = (m[:-1] @ m[-1].T).toarray().ravel()
    best = sorted(range(len(docs)), key=lambda i: -scores[i])[:k]
    words = [w for w in re.findall(r"[a-z]{4,}", q)]
    out = []
    for i in best:
        if scores[i] <= 0:
            continue
        sid, head, text = docs[i]
        t = " ".join(text.split())
        pos = min([t.lower().find(w) for w in words if t.lower().find(w) >= 0] or [0])
        start = max(0, pos - 120)
        excerpt = ("…" if start else "") + t[start:start + 420] + ("…" if start + 420 < len(t) else "")
        out.append((sid, head, excerpt, float(scores[i])))
    return out


def answer(bid, history, question, live):
    """Return (markdown answer, mode)."""
    if live:
        from agents.chat import ask
        ans, cites, _ = ask(bid, history, question)
        bad = [c["citation"] for c in cites if not c["exists"]]
        if bad:
            ans += "\n\n_Check: these citations were not found in the corpus: " + ", ".join(bad) + "._"
        return ans, "AI answer"
    hits = search(bid, question)
    if not hits:
        return "I couldn't find a section of this bill that matches. Try other words, e.g. 'appropriation' or 'composition'.", "search"
    lines = ["Here are the parts of the bill that best match your question (search mode: quotes only, no AI summary):"]
    for sid, head, ex, _ in hits:
        lines.append(f"**{head}** [{sid}]\n> {ex}")
    return "\n\n".join(lines), "search"
