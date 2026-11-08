"""Rule-based extraction of fiscal and structural facts from bill sections.

These are deterministic checks: they never invent a number. Agents use them as
anchors, and the verifier uses them to catch invented figures.
"""
import re

AMOUNT = re.compile(
    r"(?:₱|PHP|Php|P)\s?([\d,]+(?:\.\d+)?)\s*(billion|million|thousand)?"
    r"|([\d,]+(?:\.\d+)?)\s*(billion|million)\s*pesos", re.I)
SALARY_GRADE = re.compile(r"Salary\s+Grade\s*(?:\(SG\)\s*)?(\d{1,2})", re.I)
MEMBERS = re.compile(r"composed\s+of\s+([a-z\-]+|\d+)\s*(?:\((\d+)\))?\s+members", re.I)
ATTACHED = re.compile(r"attached\s+to\s+the\s+([A-Z][A-Za-z ,&\-]{3,80}?)(?:\s+for|\.|,)", re.S)
ABOLISH = re.compile(r"\b(abolish(?:ed|es|ing)?|dissolv(?:ed|es|ing)|transferred\s+to)\b", re.I)
FUNDING_SOURCE = re.compile(r"(General Appropriations Act|current appropriations|savings|unprogrammed|Contingent Fund)", re.I)

MULT = {"billion": 1e9, "million": 1e6, "thousand": 1e3}


def amounts(text):
    out = []
    for m in AMOUNT.finditer(text):
        num, unit = (m.group(1), m.group(2)) if m.group(1) else (m.group(3), m.group(4))
        try:
            v = float(num.replace(",", ""))
        except ValueError:
            continue
        v *= MULT.get((unit or "").lower(), 1)
        if v >= 1e5:  # ignore section numbers, years, small figures
            out.append({"pesos": v, "quote": text[max(0, m.start() - 60): m.end() + 40].strip()})
    return out


def facts(sections):
    """Return a dict of facts, each with the section number it came from."""
    f = {"amounts": [], "salary_grades": [], "members": [], "attached_to": [], "abolishes_or_transfers": [], "funding_source": []}
    for s in sections:
        t, no = s["text"], s["no"]
        for a in amounts(t):
            f["amounts"].append({**a, "section": no})
        for m in SALARY_GRADE.finditer(t):
            f["salary_grades"].append({"sg": int(m.group(1)), "section": no})
        for m in MEMBERS.finditer(t):
            f["members"].append({"value": m.group(2) or m.group(1), "section": no})
        for m in ATTACHED.finditer(t):
            f["attached_to"].append({"agency": " ".join(m.group(1).split()), "section": no})
        if ABOLISH.search(t):
            f["abolishes_or_transfers"].append({"section": no, "heading": s["heading"]})
        for m in FUNDING_SOURCE.finditer(t):
            f["funding_source"].append({"source": m.group(1), "section": no})
    return f


# ---------- references to existing laws inside a bill ----------
LAW_REF = re.compile(
    r"\b(?:(Republic\s+Act|R\.\s?A\.|RA)\s*(?:No\.?|Nos\.?)?\s*(\d{2,5})"
    r"|(Presidential\s+Decree|P\.\s?D\.|PD)\s*(?:No\.?)?\s*(\d{1,4})"
    r"|(Executive\s+Order|E\.\s?O\.)\s*(?:No\.?)?\s*(\d{1,4})(?:,?\s*(?:s\.|series\s+of)\s*(\d{4}))?"
    r"|(Commonwealth\s+Act|C\.\s?A\.)\s*(?:No\.?)?\s*(\d{1,4})"
    r"|(Batas\s+Pambansa|B\.\s?P\.)\s*(?:Blg\.?|Bilang)?\s*(\d{1,4}))", re.I)


def laws_cited(text):
    """Laws a bill names, as law-index IDs (RA-8435, PD-1067, EO-22[-2023]), with counts."""
    out = {}
    for m in LAW_REF.finditer(text):
        if m.group(2):
            lid = f"RA-{m.group(2)}"
        elif m.group(4):
            lid = f"PD-{m.group(4)}"
        elif m.group(6):
            lid = f"EO-{m.group(6)}" + (f"-{m.group(7)}" if m.group(7) else "")
        elif m.group(9):
            lid = f"CA-{m.group(9)}"
        else:
            lid = f"BP-{m.group(11)}"
        out[lid] = out.get(lid, 0) + 1
    return dict(sorted(out.items(), key=lambda x: -x[1]))


# ---------- "In substitution of House/Senate Bill Nos. ..." ----------
SUBST = re.compile(r"substitution\s+of\s+(House|Senate)\s+Bills?\s+Nos?\.?\s*([\d,\s&and\-]+)", re.I)
BILL_NUMS = re.compile(r"\d{1,5}")


def substitution_list(text, congress=None):
    """Bill IDs a substitute bill or committee report says it replaces."""
    out = []
    for m in SUBST.finditer(text):
        ch = "HB" if m.group(1).lower() == "house" else "SB"
        for n in BILL_NUMS.findall(m.group(2)):
            bid = f"{ch}-{congress or '20'}-{int(n)}"
            if bid not in out:
                out.append(bid)
    return out
