"""DBM-format drafts: memorandum to the Secretary and letter to the committee chair or principal author.

The layout follows DBM memoranda and position-paper letters on legislative measures (reviewed for format only):
the DBM letterhead text (Republic of the Philippines / Department of Budget and Management / General Solano Street,
San Miguel, Manila); date; MEMORANDUM FOR THE SECRETARY / Thru / From / Subject; a rule; numbered sections 1.0 to
6.0 (1.0 request, 1.1 referral to bureaus, 2.0 Salient Features, 3.0 Comments with 3.1 per bureau, 4.0
Recommendation, 5.0 attached letter, 6.0 for the Secretary's consideration) in Tahoma; the letter opens
"Greetings!" and "We respectfully submit the comments and recommendations of the Department of Budget and
Management on ...". The DBM seal is left for DBM to add on its official template (this public prototype does
not reproduce it), and there are no names of officials, no signatures and no approval boxes. Offices are
bracketed placeholders, the position stays with the reviewer, and every draft carries the AI-assisted label.

Fields are pre-filled from the reviewer-approved review and comments (no AI needed); AppraisAI can
redraft the narrative fields, and the reviewer edits everything before download.
"""
import io
import re
from datetime import date

from pipeline.compare import load

LABEL = "AI-assisted preliminary draft for DBM reviewer validation. Not an official position."
POSITION_PLACEHOLDER = "[POSITION TO BE DETERMINED BY THE REVIEWER: support / support with amendments / defer / oppose]"
SIGNATURE = "[SIGNATURE BLOCK - to be completed by DBM]"
POSITIONS = ["support", "support with amendments", "defer", "oppose"]
FONT = "Tahoma"

MEMO_FIELDS = [("date", "Date"), ("memo_for", "Memorandum for"), ("thru", "Thru"), ("from_", "From"), ("subject", "Subject"),
               ("s1", "1.0 Background"), ("s1_1", "1.1 Referral to DBM bureaus"), ("s2", "2.0 Salient features"),
               ("s3_1", "3.1 Comments of the concerned bureaus"), ("s3_2", "3.2 Observations and proposed comments"),
               ("s3_3", "3.3 Fiscal implications"), ("s4", "4.0 Recommendation"), ("s5", "5.0 Draft letter"), ("s6", "6.0 Closing")]
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


def memo_prefill(bid, review, comments=None, bureau_inputs="", status="", traice_memo=None):
    bills, _ = load()
    b = bills[bid]
    title = b["title"].rstrip(".")
    comments = [c for c in (comments or review.get("preliminary_comments", [])) if c.get("include", True)]
    lines = []
    for i, c in enumerate(comments, 1):
        sec = _section_no(c.get("section"))
        lines.append(f"{i}. " + (f"On {sec}: " if sec else "") + str(c.get("comment", "")).strip())
    fiscal = (review.get("fiscal") or {}).get("narrative", "")
    return {
        "date": today(), "memo_for": "THE SECRETARY",
        "thru": "[The Undersecretary, Legal and Legislative Group]",
        "from_": "[The Director, Budget Information Legislative and Liaison Service]",
        "subject": f"PRELIMINARY COMMENTS ON {bill_name(bid).upper()} ENTITLED \"{title.upper()}\"",
        "s1": (f"This pertains to [the request of the Committee on ______ dated ______] for the comments and recommendations of the "
               f"Department of Budget and Management (DBM) on {bill_name(bid)} entitled \"{title}.\""
               + (f" Its status as listed is: {status.lower()}." if status and not status.startswith("Status not") else "")
               + _policy_line(b)),
        "s1_1": "[BILLS referred the bill to the concerned DBM bureaus, e.g. the Budget and Management Bureau (BMB) and the "
                "Organization, Position Classification and Compensation Bureau (OPCCB), for comments on ______.]",
        "s2": ("\n\n".join(x for x in ((traice_memo or {}).get("salient", ""), (traice_memo or {}).get("related", "")) if x.strip())
               or review.get("summary", "")),
        "s3_1": bureau_inputs.strip() or "[Comments of the concerned bureaus, as received.]",
        "s3_2": "\n".join(lines) or "[Proposed comments.]",
        "s3_3": fiscal or "[Fiscal implications: to be completed from the AppraisAI review and the bureaus' comments.]",
        "s4": "In view of the foregoing, we recommend to manifest as DBM position that we " + POSITION_PLACEHOLDER,
        "s5": "Should the Secretary find merit to our recommendation, attached is the draft letter to [the Chairperson, Committee on ______, "
              "House of Representatives / Senate of the Philippines] conveying the DBM comments.",
        "s6": "For the Secretary's consideration, please. Thank you.",
    }


def apply_ai(fields, ai):
    """Merge an AppraisAI memo or letter draft (JSON with the same keys) into the fields; placeholders stay."""
    out = dict(fields)
    for k, v in (ai or {}).items():
        if k in out and isinstance(v, (str, list)) and v:
            out[k] = "\n".join(v) if isinstance(v, list) else v
    if "s4" in out and POSITION_PLACEHOLDER not in out["s4"] and not position_decided(fields):
        out["s4"] = POSITION_PLACEHOLDER          # the agent may never set the position
    return out


def position_decided(fields):
    return POSITION_PLACEHOLDER not in (fields.get("s4") or "") and "[POSITION" not in (fields.get("s4") or "")


def memo_text(fields):
    lab = dict(MEMO_FIELDS)
    head = [f"{fields.get('date', '')}", f"MEMORANDUM FOR {fields.get('memo_for', '')}", f"Thru: {fields.get('thru', '')}",
            f"From: {fields.get('from_', '')}", f"Subject: {fields.get('subject', '')}"]
    body = [f"{lab[k]}\n{fields.get(k, '')}" for k, _ in MEMO_FIELDS[5:]]
    return "\n".join(head) + "\n\n" + "\n\n".join(body) + f"\n\n{SIGNATURE}\n\n{LABEL}"


def letter_prefill(bid, memo_fields, chamber_hint=None):
    bills, _ = load()
    title = bills[bid]["title"].rstrip(".")
    chamber = "Senate of the Philippines" if bid.startswith("SB") else "House of Representatives"
    place = "Pasay City" if bid.startswith("SB") else "Quezon City"
    s4 = (memo_fields.get("s4") or "").upper()
    chosen = next((x for x in sorted(POSITIONS, key=len, reverse=True) if x.upper() in s4), None) if position_decided(memo_fields) else None
    stance = {"support": "supports the passage of the bill",
              "support with amendments": "supports the bill, subject to the comments below",
              "defer": "respectfully recommends that action on the bill be deferred, in view of the comments below",
              "oppose": "is unable to support the bill, in view of the comments below"}.get(chosen, "[states its position]")
    return {
        "date": today(),
        "addressee": "[HON. ______]",
        "office": f"[Chairperson, Committee on ______]\n{chamber}",
        "address": f"[Address], {place}",
        "subject": f"Comments on {bill_name(bid)} entitled \"{title}\"",
        "salutation": "Dear [Senator / Representative ______]:\n\nGreetings!",
        "p1": (f"We respectfully submit the comments and recommendations of the Department of Budget and Management (DBM) "
               f"on {bill_name(bid)} entitled \"{title}.\""),
        "p2": (f"After review, the DBM {stance}. In particular, we respectfully offer the following comments:\n"
               f"{memo_fields.get('s3_2', '')}"),
        "p3": memo_fields.get("s3_3", ""),
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
    heads = [("s1", "1.0", None), ("s1_1", "1.1", None), ("s2", "2.0", "Salient Features"), ("s3_1", "3.0", "Comments"),
             ("s3_2", None, None), ("s3_3", None, None), ("s4", "4.0", "Recommendation"), ("s5", "5.0", None), ("s6", "6.0", None)]
    sub = {"s3_1": "3.1 Comments of the Concerned Bureaus", "s3_2": "3.2 Observations and Proposed Comments", "s3_3": "3.3 Fiscal Implications"}
    for k, num, head in heads:
        if head:
            p = doc.add_paragraph()
            _run(p, f"{num}  ")
            _run(p, head, underline=True)
            if k in sub:
                p = doc.add_paragraph()
                p.paragraph_format.left_indent = Cm(1.0)
                _run(p, sub[k], bold=True)
            _body(doc, fields.get(k, ""))
        elif k in sub:
            p = doc.add_paragraph()
            p.paragraph_format.left_indent = Cm(1.0)
            _run(p, sub[k], bold=True)
            _body(doc, fields.get(k, ""))
        else:
            lines = str(fields.get(k, "")).split("\n")
            p = doc.add_paragraph()
            _run(p, f"{num}  ")
            _run(p, lines[0])
            if len(lines) > 1:
                _body(doc, "\n".join(lines[1:]))
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
