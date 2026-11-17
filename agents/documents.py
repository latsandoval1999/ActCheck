"""DBM-format drafts: memorandum to the Secretary and letter to the committee chair or principal author.

The layout follows DBM memoranda and position-paper letters on legislative measures (reviewed for format only):
the DBM letterhead text (Republic of the Philippines / Department of Budget and Management / General Solano Street,
San Miguel, Manila); date; MEMORANDUM FOR THE SECRETARY / Thru / From / Subject; a rule; numbered sections 1.0 to
Parts I to VII (I Background with the referral to bureaus, II Salient Features, III Related Measures and Policy
Considerations, IV Comments and Recommendations with the bureaus' comments, V Fiscal and Budgetary Requirements, VI Possible
Duplication with Existing Agencies when found, VII Recommendation), then the attached letter and closing, in Tahoma; the letter opens
"Greetings!" and "We respectfully submit the comments and recommendations of the Department of Budget and
Management on ...". The DBM seal is left for DBM to add on its official template (this public prototype does
not reproduce it), and there are no names of officials, no signatures and no approval boxes. Offices are
bracketed placeholders, the position stays with the reviewer, and every draft carries the AI-assisted label.

Fields are pre-filled from the reviewer-approved review and comments (no AI needed); ApprAIsal can
redraft the narrative fields, and the reviewer edits everything before download.
"""
import io
import re
from datetime import date

from pipeline.compare import load

LABEL = "AI-assisted preliminary draft for DBM reviewer validation. Not an official position."
POSITION_PLACEHOLDER = "[RECOMMENDATION TO BE CONFIRMED BY THE REVIEWER: no objection / no objection subject to amendments / deferment]"
SIGNATURE = "[SIGNATURE BLOCK - to be completed by DBM]"
POSITIONS = ["a", "b", "c"]          # ApprAIsal's options; the reviewer confirms one
POSITION_LABELS = {"a": "Interpose no objection", "b": "Interpose no objection, subject to amendments",
                   "c": "Constrained from supporting the proposed measure"}
FONT = "Tahoma"

MEMO_FIELDS = [("date", "Date"), ("memo_for", "Memorandum for"), ("thru", "Thru"), ("from_", "From"), ("subject", "Subject"),
               ("s1", "I. Background"), ("s2", "II. Salient Features"), ("s3", "III. Related Measures and Policy Considerations"),
               ("s4", "IV. Comments and Recommendations"), ("s4_b", "Comments of the concerned bureaus"),
               ("s5", "V. Fiscal and Budgetary Requirements"), ("s6", "VI. Possible Duplication with Existing Agencies"),
               ("s7", "VII. Recommendation"), ("s8", "Draft letter"), ("s9", "Closing")]
LETTER_FIELDS = [("date", "Date"), ("addressee", "Addressee"), ("office", "Committee / office"), ("address", "Address"),
                 ("subject", "Subject"), ("salutation", "Salutation"), ("p1", "Opening paragraph"), ("p2", "DBM comments"),
                 ("p3", "Fiscal implications"), ("p4", "Closing paragraph"), ("closing", "Complimentary close")]


def today():
    d = date.today()
    return f"{d.strftime('%B')} {d.day}, {d.year}"


def bill_name(bid):
    ch, c, n = bid.split("-")
    return f"{'House' if ch == 'HB' else 'Senate'} Bill No. {n}"


def _section_no(s):
    m = re.search(r":s(\d+)$", s or "")
    return f"Section {m.group(1)}" if m else ""


def _policy_line(b):
    from pipeline import policy
    return policy.memo_line({"title": b.get("title", ""), "congress": b.get("congress")})


def memo_prefill(bid, parts=None, status="", referrals=None, bureau_inputs=None):
    """The memorandum, Parts I to VII, from the three agents' reviewed outputs (no AI needed).
    parts: {"context", "salient", "related", "comments", "fiscal", "duplication", "recommendation"}.
    The recommendation (Part VII) stays a placeholder until the reviewer confirms one of ApprAIsal's options."""
    bills, _ = load()
    b = bills[bid]
    title = b["title"].rstrip(".")
    parts = parts or {}
    refs = referrals or []
    nm = [f"the {r.get('name', r.get('bureau', ''))} ({r.get('bureau', '')})" for r in refs]
    ref_line = ((" The bill was referred to " + (", ".join(nm[:-1]) + " and " + nm[-1] if len(nm) > 1 else nm[0]) + " for their comments.")
                if refs else " [The bill was referred to the concerned DBM bureaus for their comments.]")
    bur = "\n".join(f"The {k} commented that {v.strip()}" if not v.strip().lower().startswith("the ") else v.strip()
                     for k, v in (bureau_inputs or {}).items() if v and v.strip())
    return {
        "date": today(), "memo_for": "THE SECRETARY",
        "thru": "[The Undersecretary, Legal and Legislative Group]",
        "from_": "[The Director, Budget Information Legislative Service]",
        "subject": f"PRELIMINARY COMMENTS ON {bill_name(bid).upper()} ENTITLED \"{title.upper()}\"",
        "s1": (f"This pertains to [the request of the Committee on ______ dated ______] for the comments and recommendations of the "
               f"Department of Budget and Management (DBM) on {bill_name(bid)} entitled \"{title}.\""
               + (f" Status as listed: {status.strip().rstrip('.')}." if status and not status.startswith("Status not") else "")
               + ref_line + ("\n" + parts["context"] if parts.get("context") else "")),
        "s2": parts.get("salient", "") or "[Salient features from TrAIce.]",
        "s3": parts.get("related", "") or "[Related measures and policy considerations from TrAIce.]",
        "s4": parts.get("comments", "") or "[Comments and recommendations from CompAIre.]",
        "s4_b": bur or "[Comments of the concerned bureaus, as received.]",
        "s5": parts.get("fiscal", "") or "[Fiscal and budgetary requirements from ApprAIsal.]",
        "s6": parts.get("duplication", ""),
        "s7": POSITION_PLACEHOLDER,
        "s8": "Should the Secretary find merit to our recommendation, attached is the draft letter to [the Chairperson, Committee on ______, "
              "House of Representatives / Senate of the Philippines] conveying the DBM comments.",
        "s9": "For the Secretary's consideration, please. Thank you.",
        "_proposed": parts.get("recommendation", ""),
    }


def set_recommendation(fields, text):
    """The reviewer confirms Part VII (ApprAIsal's proposal, as edited)."""
    return dict(fields, s7=text)


def apply_ai(fields, ai):
    """Merge an ApprAIsal memo or letter draft (JSON with the same keys) into the fields; placeholders stay."""
    out = dict(fields)
    for k, v in (ai or {}).items():
        if k in out and isinstance(v, (str, list)) and v:
            out[k] = "\n".join(v) if isinstance(v, list) else v
    if "s7" in out and POSITION_PLACEHOLDER not in out["s7"] and not position_decided(fields):
        out["s7"] = POSITION_PLACEHOLDER          # the agent may propose, but only the reviewer sets the recommendation
    return out


def position_decided(fields):
    s7 = fields.get("s7") or ""
    return bool(s7.strip()) and POSITION_PLACEHOLDER not in s7 and "[RECOMMENDATION" not in s7 and "[POSITION" not in s7


def memo_text(fields):
    lab = dict(MEMO_FIELDS)
    head = [f"{fields.get('date', '')}", f"MEMORANDUM FOR {fields.get('memo_for', '')}", f"Thru: {fields.get('thru', '')}",
            f"From: {fields.get('from_', '')}", f"Subject: {fields.get('subject', '')}"]
    body = [f"{lab[k]}\n{fields.get(k, '')}" for k, _ in MEMO_FIELDS[5:] if fields.get(k) or k != "s6"]
    return "\n".join(head) + "\n\n" + "\n\n".join(body) + f"\n\n{SIGNATURE}\n\n{LABEL}"


def _unnumber(text):
    """Memo paragraph numbers (4.1, 5.2 ...) do not belong in the letter; subheadings stay."""
    return "\n".join(re.sub(r"^\s*\d+\.\d+\.?\s+", "", ln) for ln in (text or "").split("\n")).strip()


def letter_prefill(bid, memo_fields, chamber_hint=None):
    bills, _ = load()
    title = bills[bid]["title"].rstrip(".")
    chamber = "Senate of the Philippines" if bid.startswith("SB") else "House of Representatives"
    place = "Pasay City" if bid.startswith("SB") else "Quezon City"
    s7 = memo_fields.get("s7") or ""
    stance = ("[states its position]" if not position_decided(memo_fields) else
              "interposes no objection to the proposed measure, subject to the incorporation of the comments below" if "subject to" in s7 else
              "interposes no objection to the proposed measure" if "no objection" in s7 else
              "respectfully recommends that further consideration of the measure be deferred until the issues below are addressed"
              if "deferred" in s7 else "[states its position]")
    return {
        "date": today(),
        "addressee": "[HON. ______]",
        "office": f"[Chairperson, Committee on ______]\n{chamber}",
        "address": f"[Address], {place}",
        "subject": f"Comments on {bill_name(bid)} entitled \"{title}\"",
        "salutation": "Dear [Senator / Representative ______]:\n\nGreetings!",
        "p1": (f"We respectfully submit the comments and recommendations of the Department of Budget and Management (DBM) "
               f"on {bill_name(bid)} entitled \"{title}.\""),
        "p2": f"After review, the DBM {stance}. In particular, we respectfully offer the following comments:\n" + _unnumber(memo_fields.get("s4", "")),
        "p3": "\n".join(x for x in (_unnumber(memo_fields.get("s5", "")), _unnumber(memo_fields.get("s6", ""))) if x),
        "p4": "We trust that these comments will be considered in the Committee's deliberations. The DBM remains available to provide "
              "further technical assistance on the measure.\n\nThank you very much.",
        "closing": "Very truly yours,",
    }


def letter_text(fields):
    return "\n\n".join(str(fields.get(k, "")) for k, _ in LETTER_FIELDS) + f"\n\n{SIGNATURE}\n\n{LABEL}"


# ---------------- Word output ----------------
def _doc():
    from docx import Document
    from docx.shared import Pt, Cm
    from docx.oxml.ns import qn
    doc = Document()
    for s in doc.sections:
        s.top_margin, s.bottom_margin, s.left_margin, s.right_margin = Cm(2.2), Cm(2.0), Cm(2.5), Cm(2.5)
    st = doc.styles["Normal"]
    st.font.name, st.font.size = FONT, Pt(11)
    st.element.rPr.rFonts.set(qn("w:eastAsia"), FONT)
    st.paragraph_format.space_after = Pt(6)
    return doc


def _run(p, text, bold=False, size=None, italic=False, caps=False, underline=False):
    from docx.shared import Pt
    r = p.add_run(text)
    r.bold, r.italic, r.underline = bold, italic, underline
    r.font.name = FONT
    r.font.all_caps = caps
    if size:
        r.font.size = Pt(size)
    return r


LETTERHEAD = ("REPUBLIC OF THE PHILIPPINES", "DEPARTMENT OF BUDGET AND MANAGEMENT", "GENERAL SOLANO STREET, SAN MIGUEL, MANILA")
SEAL_NOTE = "[DBM seal: added by DBM on its official template]"


def _letterhead(doc, address=True):
    """DBM letterhead text in a serif face, as on DBM issuances; the seal is left to DBM's official template."""
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt
    serif = "Bookman Old Style"
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    p.paragraph_format.space_after = Pt(2)
    _run(p, SEAL_NOTE, italic=True, size=7)
    for i, (txt, size, bold) in enumerate(((LETTERHEAD[0], 10.5, False), (LETTERHEAD[1], 13, True), (LETTERHEAD[2], 7.5, False))):
        if i == 2 and not address:
            continue
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.CENTER
        p.paragraph_format.space_after = Pt(0)
        r = _run(p, txt, bold=bold, size=size)
        r.font.name = serif
        r._element.rPr.rFonts.set(__import__("docx.oxml.ns", fromlist=["qn"]).qn("w:eastAsia"), serif)
    p = doc.add_paragraph()
    p.alignment = WD_ALIGN_PARAGRAPH.CENTER
    _run(p, "DRAFT · " + LABEL, italic=True, size=8)


def _footer(doc):
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    p = doc.sections[0].footer.paragraphs[0]
    p.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    _run(p, LABEL + "   Page ", size=8, italic=True)
    for code in ("PAGE", None, "NUMPAGES"):
        if code is None:
            _run(p, " of ", size=8, italic=True)
            continue
        fld = OxmlElement("w:fldSimple")
        fld.set(qn("w:instr"), code)
        r = OxmlElement("w:r")
        t = OxmlElement("w:t")
        t.text = "1"
        r.append(t)
        fld.append(r)
        p._p.append(fld)


def _rule(doc):
    from docx.oxml import OxmlElement
    from docx.oxml.ns import qn
    p = doc.add_paragraph()
    pPr = p._p.get_or_add_pPr()
    bdr = OxmlElement("w:pBdr")
    b = OxmlElement("w:bottom")
    for k, v in (("w:val", "single"), ("w:sz", "8"), ("w:space", "1"), ("w:color", "000000")):
        b.set(qn(k), v)
    bdr.append(b)
    pPr.append(bdr)


def _body(doc, text, indent_cm=1.0):
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Cm
    for para in str(text or "").split("\n"):
        if not para.strip():
            continue
        p = doc.add_paragraph()
        p.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
        p.paragraph_format.left_indent = Cm(indent_cm)
        _run(p, para.strip())


def memo_docx(fields):
    from docx.shared import Cm
    doc = _doc()
    _letterhead(doc, address=False)
    _footer(doc)
    doc.add_paragraph(fields.get("date", ""))
    p = doc.add_paragraph()
    _run(p, f"MEMORANDUM FOR {fields.get('memo_for', '')}", bold=True)
    t = doc.add_table(rows=0, cols=3)
    for k, lab in (("thru", "Thru"), ("from_", "From"), ("subject", "Subject")):
        cells = t.add_row().cells
        cells[0].text, cells[1].text = lab, ":"
        r = cells[2].paragraphs[0]
        _run(r, fields.get(k, ""), bold=(k == "subject"))
    t.autofit = False
    for i, w in enumerate((Cm(2.4), Cm(0.6), Cm(13))):
        t.columns[i].width = w
        for cell in t.columns[i].cells:
            cell.width = w
    _rule(doc)
    for k, head in MEMO_FIELDS[5:]:
        val = fields.get(k, "")
        if k == "s6" and not str(val).strip():
            continue                                   # Part VI only when a duplication was found
        if k in ("s8", "s9"):
            _body(doc, val, indent_cm=0)
            continue
        p = doc.add_paragraph()
        if k == "s4_b":
            p.paragraph_format.left_indent = Cm(1.0)
            _run(p, head, bold=True, italic=True)
        else:
            _run(p, head, bold=True)
        for line in str(val or "").split("\n"):
            if not line.strip():
                continue
            if re.match(r"^On (the )?\w", line.strip()) and len(line) < 110 and not line.strip().endswith("."):
                q = doc.add_paragraph()
                q.paragraph_format.left_indent = Cm(1.0)
                _run(q, line.strip(), bold=True, italic=True)
            else:
                _body(doc, line)
    doc.add_paragraph()
    p = doc.add_paragraph()
    _run(p, SIGNATURE, italic=True)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def letter_docx(fields):
    doc = _doc()
    _letterhead(doc)
    _footer(doc)
    doc.add_paragraph(fields.get("date", ""))
    p = doc.add_paragraph()
    _run(p, fields.get("addressee", ""), bold=True)
    for line in (fields.get("office", "") + "\n" + fields.get("address", "")).split("\n"):
        if line.strip():
            q = doc.add_paragraph(line.strip())
            q.paragraph_format.space_after = 0
    doc.add_paragraph()
    for line in str(fields.get("salutation", "")).split("\n"):
        if line.strip():
            doc.add_paragraph(line.strip())
    for k in ("p1", "p2", "p3", "p4"):
        _body(doc, fields.get(k, ""), indent_cm=0)
    doc.add_paragraph(fields.get("closing", ""))
    doc.add_paragraph()
    p = doc.add_paragraph()
    _run(p, SIGNATURE, italic=True)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
