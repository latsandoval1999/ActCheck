"""Parse a bill's plain text into metadata, explanatory note and sections.

Works on text from pdftotext -layout or from OCR. House bills have no line
numbers; Senate bills usually carry a line number at the start of each line,
which is removed first.
"""
import re

SENATE_LINENO = re.compile(r"^\s{0,6}\d{1,3}(?=\s{2,}|\t)")
SECTION_HDR = re.compile(
    r"^\s*(?:SEC\.?TION|SECTION|Section|SEC|Sec)\s*\.?\s*(\d{1,3})\s*[\.\-–:]?\s*(.*)$")
ENACTING = re.compile(r"Be\s+it\s+enacted", re.I)
TITLE = re.compile(r"(AN\s+ACT\b.*?)(?:\n\s*\n|EXPLANATORY\s+NOTE)", re.S)
PAGE_MARK = re.compile(r"^===== \[page \d+\] =====$")


def clean(text: str) -> str:
    lines = []
    for ln in text.replace("\f", "\n").replace("\u200b", "").splitlines():
        if PAGE_MARK.match(ln.strip()):
            continue
        ln = SENATE_LINENO.sub("", ln)
        lines.append(ln.rstrip())
    out = "\n".join(lines)
    out = re.sub(r"\n{3,}", "\n\n", out)
    return out


def _heading(rest: str) -> str:
    # "Short Title. - This Act shall..." -> "Short Title"
    m = re.match(r"(.{2,120}?)\s*[\.\-–—:]+\s*[\-–—]?\s+(?=[A-Z\"“(])", rest)
    return (m.group(1) if m else rest[:80]).strip(" .-–—:")


def parse_bill(text: str) -> dict:
    t = clean(text)
    m = TITLE.search(t)
    title = " ".join(m.group(1).split()) if m else ""
    em = ENACTING.search(t)
    note = t[:em.start()] if em else ""
    body = t[em.start():] if em else t
    sections, cur = [], None
    for ln in body.splitlines():
        h = SECTION_HDR.match(ln)
        n = int(h.group(1)) if h else 0
        # accept the next section number, allowing small gaps from OCR misses
        if h and (cur is None or cur["no"] < n <= cur["no"] + 3):
            if cur:
                sections.append(cur)
            cur = {"no": int(h.group(1)), "heading": _heading(h.group(2)), "lines": [ln.strip()]}
        elif cur:
            cur["lines"].append(ln.strip())
    if cur:
        sections.append(cur)
    for s in sections:
        s["text"] = " ".join(x for x in s.pop("lines") if x).strip()
    en = note.find("EXPLANATORY NOTE")
    return {
        "title": title,
        "explanatory_note": " ".join(note[en:].split()) if en >= 0 else "",
        "sections": sections,
        "n_sections": len(sections),
    }
