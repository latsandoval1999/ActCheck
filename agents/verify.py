"""Deterministic checks on agent output. No AI involved.

Every claim an agent makes must cite a section ID (e.g. "HB-20-2322:s13") and
quote a short passage from it. These checks catch the main failure modes the
portfolio tests for: fabricated citations, misquotes, and invented figures.
"""
import re
from difflib import SequenceMatcher

from pipeline.compare import load

NUM = re.compile(r"(?:₱|PHP|P)\s?[\d,]+(?:\.\d+)?\s*(?:billion|million)?|\b\d[\d,]*(?:\.\d+)?\s*(?:billion|million)\b", re.I)


def _norm(s):
    return re.sub(r"\s+", " ", re.sub(r"[“”\"'’‘]", "", s.lower())).strip()


def section_text(section_id):
    """Text behind a citation: a section ("HB-20-2322:s5"), a bill title ("meta:HB-19-9663")
    or a law title ("law:RA-8435"). None if the source does not exist."""
    if section_id.startswith("meta:") or section_id.startswith("law:"):
        from agents.research import bill_index, law_index
        kind, key = section_id.split(":", 1)
        df = bill_index() if kind == "meta" else law_index()
        row = df[df["id"] == key]
        if not len(row):
            return None
        r = row.iloc[0]
        return (r.get("short_title", "") + " " + r["title"]).strip()
    if section_id.endswith(":note"):  # explanatory note / front matter of a bill or report
        bills, _ = load()
        b = bills.get(section_id.rsplit(":", 1)[0])
        return (b.get("front_matter", "") + " " + b.get("explanatory_note", "")) if b else None
    _, secs = load()
    bill = section_id.split(":")[0]
    for s in secs.get(bill, []):
        if s["id"] == section_id:
            return s["text"]
    return None


def quote_found(quote, text, threshold=0.85):
    """True if `quote` appears in `text`, allowing small OCR differences."""
    q, t = _norm(quote), _norm(text)
    if not q:
        return False
    if q in t:
        return True
    best = 0.0
    step = max(1, len(q) // 4)
    for i in range(0, max(1, len(t) - len(q) + 1), step):
        best = max(best, SequenceMatcher(None, q, t[i:i + len(q)]).ratio())
        if best >= threshold:
            return True
    return False


def check_citations(claims):
    """claims: list of {"claim", "section", "quote"}. Adds 'check' to each."""
    out = []
    for c in claims:
        sid, quote = c.get("section", ""), c.get("quote", "")
        text = section_text(sid) if sid else None
        if not sid:
            status = "no citation"
        elif text is None:
            status = "section does not exist"
        elif not quote:
            status = "no quote"
        elif quote_found(quote, text):
            status = "verified"
        else:
            status = "quote not found in section"
        out.append({**c, "check": status})
    return out


def numbers_supported(output_text, source_texts):
    """List peso amounts in the output that appear in none of the sources."""
    src = _norm(" ".join(source_texts))
    missing = []
    for m in NUM.finditer(output_text):
        digits = re.sub(r"[^\d]", "", m.group(0))
        if digits and digits not in re.sub(r"[^\d ]", "", src).replace(" ", ""):
            missing.append(m.group(0))
    return missing


BANNED = [r"\bapproved by\b", r"\bsigned\b", r"\bsecretary\s+[A-Z][a-z]+", r"\bwe recommend (?:approval|disapproval)\b"]


def governance_flags(report_text):
    """Flags text a preliminary AI draft must not contain (signatures, final positions)."""
    return [p for p in BANNED if re.search(p, report_text, re.I)]
