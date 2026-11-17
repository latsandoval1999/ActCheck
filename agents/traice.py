"""TrAIce (Agent 1), version 3: identify the measure, trace its history, map related bills and laws, and draft its
salient features, linkages and fiscal requirements as the primary output that feeds the memo and the later agents.

Two sources fill the same structure:
  * rule_draft(): ActCheck's own draft, made by code from the bill text and the data sets (no AI, no cost, instant);
  * a TrAIce run by Claude (prompt agents/prompts/p1_research.md), saved with the bill or in data/agent_runs/.
normalize() turns either, or an output saved in the earlier format, into what the Review workspace shows.
"""
import json
import re
from pathlib import Path

from pipeline.compare import load

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "data" / "agent_runs"

# relationship labels shown to reviewers (stored as written; earlier outputs are mapped on display)
LABELS = ["Filed in a past Congress", "Same bill, filed again this Congress", "Merged into this bill",
          "Counterpart in the other chamber", "Alternative proposal", "Template it follows",
          "Not related (similar wording only)"]
LAW_LABELS = ["Amends or repeals", "Overlapping functions", "Referenced in the bill", "Template it follows"]
OLD = {"earlier version": LABELS[0], "refiled near-copy": LABELS[1], "consolidated into this substitute": LABELS[2],
       "counterpart in other chamber": LABELS[3], "counterpart in other chamber (near-identical text)": LABELS[3],
       "competing design": LABELS[4], "same subject (competing or related design)": LABELS[4],
       "precedent or model": LABELS[5], "unrelated": LABELS[6], "possibly related": LABELS[6],
       "existing law affected": LAW_LABELS[1]}
ORDER = {lab: i for i, lab in enumerate(LABELS)}

BPF_FOCUS = {
    "Human capital development": "equitable access to quality education, the Universal Health Care system and better targeting of social protection",
    "Food security": "climate-resilient and smart agriculture, targeted infrastructure and mechanization, and Farm and Fisheries Clustering and Consolidation (F2C2)",
    "Infrastructure development": "timely completion of flagship and high-impact infrastructure, climate-resilient design and public-private partnerships",
    "Digitalization": "interoperable digital platforms, the eGovPH system and digital infrastructure for unserved areas",
    "Environment, climate, and disaster resilience": "nature-based solutions, coastal and marine conservation, and stronger forecasting and early warning",
    "Implementation of full devolution to LGUs": "a calibrated transition to full devolution, capacity building and fiscal support for disadvantaged LGUs",
}
FOCUS = {
    "Government organization and mandates": "how {e}'s proposed functions fit with those of existing agencies and bodies, and how the measure relates to the government's intent to streamline agencies and reduce overlapping mandates under the Government Optimization Act (RA No. 12231)",
    "Public-sector compensation and personnel": "the proposed positions, salary grades and benefits against the compensation and position classification system, and the fiscal space for personnel services",
    "Public programs and benefits": "the coverage, beneficiaries and funding requirements of the proposed program, and possible overlap with existing programs",
    "Public facilities and infrastructure": "the implementing agency and source of funds of the proposed facility, and its priority within the agency's regular budget",
    "Appropriations": "the amount and source of the appropriation and its consistency with the annual budget process",
    "Taxation and revenue": "the revenue effect of the measure and its consistency with the government's fiscal program",
    "Tariffs and customs duties": "the revenue effect of the measure and its consistency with the government's fiscal program",
    "Public borrowing and debt": "the debt implications of the measure and its consistency with the medium-term fiscal program",
    "Emergency response and recovery": "the funding mechanism for response and recovery and its relation to the existing disaster risk reduction and management fund",
}


def _doc(bid):
    ch, c, n = bid.split("-")[:3]
    return {"HB": f"HB No. {n}", "SB": f"SB No. {n}"}.get(ch, bid)


def _short(bid):
    bills, _ = load()
    if bid in bills and bid.split("-")[0] not in ("HB", "SB"):
        return bills[bid].get("label", bid)
    return {"HB": "HB", "SB": "SB", "RA": "RA", "PD": "PD", "EO": "EO", "CR": "Committee report"}.get(bid.split("-")[0], "") + \
        (" " + bid.split("-")[2] if bid.split("-")[0] in ("HB", "SB") else " " + "-".join(bid.split("-")[1:]))


def _doc_name_law(i):
    p = str(i).split("-")
    return f"{p[0]} No. {'-'.join(p[1:])}" if len(p) > 1 else str(i)


def sections(bid):
    _, secs = load()
    return secs.get(bid, [])


def sec_ref(bid, no):
    for s in sections(bid):
        if str(s["no"]) == str(no):
            return f"Section {s['no']} ({s['heading']})"
    return f"Section {no}"


def _find(bid, pattern):
    return next((s for s in sections(bid) if re.search(pattern, s["heading"], re.I)), None)


def display_label(label, target_id, other_id):
    lab = OLD.get(str(label).lower().strip(), label)
    if lab == LABELS[3]:
        o = str(other_id)
        if o.startswith(("CR", "SUB")):
            fm = ((load()[0].get(o) or {}).get("front_matter") or "")[:800].upper()
            o = "SB" if "SENATE" in fm else "HB" if "HOUSE OF REPRESENTATIVES" in fm else o
        return "Senate version" if o.startswith("SB") else "House version" if o.startswith("HB") else lab
    return lab


def _entity_name(bid, fallback):
    s1 = _find(bid, r"short title")
    m = re.search(r"known as the\s*[\"“]?(.+?)[\"”]?\s*(?:\(|Act\b)", (s1 or {}).get("text", ""), re.I)
    name = (m.group(1) if m else fallback or "").strip(" ,.\"“”")
    return re.sub(r"\s+Act$", "", name)


def _duration(bid):
    s = _find(bid, r"duration|term of|sunset|lifetime")
    m = re.search(r"\b([a-z]+)\s*\((\d+)\)\s*years?", (s or {}).get("text", ""), re.I)
    return (f"{m.group(1).lower()}-year", s) if m else ("", None)


COMMON = set("a an the of to in on and or for by as at be is are its it any all per not no may with from into such than".split())


def _noise(tok):
    w = tok.strip(",.;:()")
    if not w:
        return True
    if re.search(r"[&£@%¢§]", w) or re.fullmatch(r"\d{1,3}|\d[A-Za-z]{1,2}", w):
        return True
    if len(w) <= 2 and w[:1].isupper() and w not in ("A", "I"):
        return True
    if len(w) <= 4 and (sum(c.isupper() for c in w) >= 2 or (w[:1].islower() and any(c.isupper() for c in w[1:]))):
        return True
    return len(w) <= 3 and w.islower() and w not in COMMON


def clean_ocr(t):
    """Drop runs of scanning noise (line numbers and broken letters) from text read off a scanned page."""
    toks = (t or "").split()
    keep, run = [], []
    for tok in toks:
        if _noise(tok):
            run.append(tok)
            continue
        if len(run) < 4:
            keep += run
        run = []
        keep.append(tok)
    if len(run) < 4:
        keep += run
    return " ".join(keep)


def _purpose(bid):
    s = _find(bid, r"creation|establishment|created") or _find(bid, r"declaration of policy")
    t = clean_ocr((s or {}).get("text", ""))
    m = re.search(r"\bto (undertake|serve|review|assess|ensure|provide|promote|formulate|implement|lead|coordinate|oversee)\b(.{20,420}?)(\.|;|$)", t, re.I)
    if not m:
        return ""
    p = (m.group(1).lower() + m.group(2)).strip(" ,")
    p = re.sub(r",?\s*for the purpose of (\w+?)ing\b", lambda x: " and " + _verb(x.group(1) + "ing"), p)
    p = re.sub(r",?\s*with the end(?: in view)? of (\w+?)ing\b", lambda x: " to " + _verb(x.group(1) + "ing"), p)
    return p


E_STEMS = ("at", "iz", "is", "id", "ir", "ar", "or", "ur", "uc", "ov", "ib", "um", "am", "ag", "ul", "rv", "lv", "ot", "et", "nc", "rc")
VERB_FIX = {"defining": "define", "maintaining": "maintain", "obtaining": "obtain", "containing": "contain", "using": "use",
            "renaming": "rename", "making": "make", "giving": "give", "having": "have", "imposing": "impose", "reviewing": "review"}


def _verb(word):
    """'promoting' -> 'promote', 'establishing' -> 'establish'."""
    w = word.lower()
    if w in VERB_FIX:
        return VERB_FIX[w]
    if not w.endswith("ing"):
        return w
    st = w[:-3]
    if len(st) > 2 and st[-1] == st[-2] and st[-1] not in "ls":
        st = st[:-1]
    return st + "e" if st.endswith(E_STEMS) else st


SMALL = {"of", "on", "and", "the", "for", "in", "to", "a", "an", "at", "by", "with"}


def title_case(t):
    words = (t or "").lower().split()
    return " ".join(w if (i and w in SMALL) else (w.upper() if re.fullmatch(r"\(?[a-z]{2,6}\)?", w) and w.strip("()") in {"dict", "deped"} else w.capitalize())
                    for i, w in enumerate(words))


def inconsistencies(bid):
    """Provisions that do not match each other, found by rule (e.g. the body's name differs between sections)."""
    out = []
    s1, s4 = _find(bid, r"short title"), _find(bid, r"creation|establishment")
    if s1 and s4:
        n1 = _entity_name(bid, "")
        m = re.search(r"created (?:an?|the)\s+(.+?)(?:,|\s+hereinafter|\s+to\b)", s4["text"], re.I)
        n4 = (m.group(1) if m else "").strip()
        norm = lambda x: re.sub(r"[^a-z]", "", x.lower())  # noqa: E731
        if n1 and n4 and norm(n1) not in norm(n4) and norm(n4) not in norm(n1):
            out.append(f"The name of the body differs between {sec_ref(bid, s1['no'])} (\"{n1}\") and {sec_ref(bid, s4['no'])} (\"{n4}\").")
    return out


def _sources(t):
    src = []
    if re.search(r"Senate and (?:the )?House", t, re.I):
        src.append("available appropriations of the Senate and the House of Representatives")
    m = re.search(r"(?:current|available|existing) appropriations of the ((?:Department|Office|Commission|Authority|National|Philippine)[\w ,\-]+?)(?=,|\.|\s+and\b|\s+which\b)", t)
    if m and not src:
        src.append("current appropriations of the " + m.group(1).strip())
    gaa = bool(re.search(r"General Appropriations", t, re.I))
    return src, gaa


def fiscal(bid, facts):
    """Fiscal requirements stated in the bill, with the section each comes from."""
    out = []
    ap = _find(bid, r"appropriation|funding")
    if ap:
        amt = next((a for a in facts.get("amounts", []) if str(a.get("section")) == str(ap["no"])), None)
        src, gaa = _sources(ap["text"])
        out.append({"item": "Initial funding", "detail": (f"₱{amt['pesos']:,.0f}" if amt else "Amount necessary (no amount stated)")
                    + (", charged against " + src[0] if src else ""), "section": sec_ref(bid, ap["no"]),
                    "amount": amt["pesos"] if amt else None, "source": src[0] if src else "", "gaa": gaa})
        if gaa:
            out.append({"item": "Continuing funding", "detail": "Included in the annual General Appropriations Act", "section": sec_ref(bid, ap["no"])})
    for sg in facts.get("salary_grades", [])[:6]:
        s = next((x for x in sections(bid) if str(x["no"]) == str(sg["section"])), None)
        role = re.search(r"rank,? privileges,? and emoluments of (?:an? )?([A-Z][A-Za-z ]+?)(?:\s*\(|,|\.)", (s or {}).get("text", ""))
        out.append({"item": "Position", "detail": f"{role.group(1).strip() if role else 'Head'} (Salary Grade {sg['sg']})",
                    "section": sec_ref(bid, sg["section"]), "heading": (s or {}).get("heading", "")})
    comp = _find(bid, r"composition|members")
    if comp and re.search(r"receive no compensation", comp["text"], re.I):
        out.append({"item": "Members", "detail": "No compensation; travelling, communications and other necessary expenses allowed", "section": sec_ref(bid, comp["no"])})
    for hd in (r"secretariat", r"research arm", r"advisory"):
        s = _find(bid, hd)
        if s:
            out.append({"item": "Support body", "detail": s["heading"], "section": sec_ref(bid, s["no"])})
    return out


def rule_draft(bid, pack, row=None, pctx=None, category=""):
    """ActCheck's draft of the TrAIce output, made by code (no AI)."""
    bills, _ = load()
    b = bills.get(bid, {})
    prof = pack["profile"]
    row = row or {}
    doc = _doc(bid)
    short = re.search(r"\(([A-Z]{3,})\)", (_find(bid, r"short title") or {}).get("text", ""))
    sname = _entity_name(bid, "")
    body = r"\b(Commission|Department|Office|Authority|Council|Board|Institute|Agency|Bureau|Cent(?:er|re)|University|College|Corporation|Administration)\b"
    entity = sname if (sname and re.search(body, sname)) else (title_case(prof.get("entity", "")) if prof.get("entity") else sname)
    if entity and short and short.group(1) not in entity:
        entity += f" ({short.group(1)})"
    eshort = short.group(1) if short else (entity or "the proposed body")
    dur, dsec = _duration(bid)
    purpose = _purpose(bid)
    members = next((m["value"] for m in (b.get("facts") or {}).get("members", [])), "")
    creates = bool(prof.get("entity"))

    # 1. proposal and alignment
    if creates:
        art = ("a " + dur + " ") if dur else ("the " if re.match(r"(Department|Office|Philippine|National)\b", entity or "") else "")
        proposal = f"{doc} proposes to establish {art}{entity}" + (f" to {purpose}" if purpose else "") + "."
    else:
        t0 = b.get("title") or prof.get("title", "")
        if len(t0) < 20:
            t0 = row.get("title") or t0
        t = re.sub(r"^AN ACT\s+", "", t0, flags=re.I).rstrip(".").lower()
        t = re.sub(r"\b([a-z]+ing)\b", lambda x: _verb(x.group(1)) if x.start() == 0 or t[x.start() - 2:x.start()] in (", ", "d ") else x.group(1), t)
        proposal = f"{doc} seeks to {t}." if t else f"{doc} is a proposed measure."
    pctx = pctx or {}
    areas = [a["area"] for a in pctx.get("bpf_2027_priority_areas", [])]
    led = pctx.get("ledac", [])
    focus = FOCUS.get(category, "the budgetary implications of the measure and the agencies concerned").format(e=eshort)
    align = f"Under {title_case(category) if category else 'its bill type'}, the review should examine {focus}."
    if areas:
        align += (f" The bill's primary alignment is with {title_case(areas[0])} in the FY 2027 Budget Priorities Framework"
                  + (f", particularly its focus on {BPF_FOCUS[areas[0]]}" if areas[0] in BPF_FOCUS else "") + ".")
    else:
        align += " No direct match with the FY 2027 Budget Priorities Framework priority areas was found from its title."
    if led:
        align += f" It relates by title to item {led[0]['no']} of the LEDAC Common Legislative Agenda ({led[0]['measure']})."

    # 2. related bills (rules) and history
    rel = []
    tch, tcong = bid.split("-")[0], str(b.get("congress") or prof.get("congress") or "")
    etype = re.search(r"(Congressional Commission|Commission|Council|Authority|Department|Office|Board|Institute|Bureau|Corporation|Administration)", entity or "")
    subj = {w.lower() for w in re.findall(r"[A-Za-z]{5,}", entity or "")} - {
        "congressional", "commission", "council", "authority", "department", "office", "board", "institute", "bureau", "national",
        "philippine", "philippines", "corporation", "administration", "center", "centre", "regulatory", "development"}
    for r in pack["related"]:
        if r.get("similarity") is None and not r.get("baseline_label"):
            continue
        sim = r.get("similarity")
        textual = sim is not None and "title" not in r["source"]
        och = (bills.get(r["id"]) or {}).get("chamber") or r["id"].split("-")[0]
        same_ch = och == tch or (r["id"].startswith("CR") and False)
        cong = str(r.get("congress") or r["id"].split("-")[1])
        ttl = (bills.get(r["id"]) or {}).get("title") or r.get("title", "")
        lab = OLD.get(r["baseline_label"].lower(), LABELS[6])
        if lab == LABELS[2] or r["source"].startswith("named in substitution"):
            lab = LABELS[2]
        elif textual and cong == tcong and r["id"][:2] == tch and sim >= 0.7:
            lab = LABELS[2] if b.get("kind") == "substitute" else LABELS[1]
        elif not textual and (sim or 0) >= 0.9 and r["id"][:2] in ("HB", "SB"):
            # an (almost) identical title, text not available
            lab = (LABELS[0] if cong < tcong else (LABELS[2] if b.get("kind") == "substitute" else LABELS[1]) if r["id"][:2] == tch else LABELS[3]) \
                if cong.isdigit() and tcong.isdigit() else lab
        elif textual and lab == LABELS[4] and sim < 0.3:
            lab = LABELS[6]
        # same kind of body on a different subject: a template, not a related measure
        if etype and subj and lab in (LABELS[4], LABELS[6]) and etype.group(1).upper() in ttl.upper() \
                and not any(w.upper() in ttl.upper() for w in subj):
            lab = LABELS[5]
        if lab == LABELS[6] and (sim or 0) < 0.35:
            continue
        base = (f"{sim:.0%} of wording in common" if textual else
                "Same title (text not available)" if (sim or 0) >= 0.9 else "Title match only (text not available)")
        why = base + {
            LABELS[0]: f"; filed in the {cong}th Congress.",
            LABELS[1]: "; near-identical text in the same chamber and Congress.",
            LABELS[2]: ("; named in the substitution clause." if r["source"].startswith("named") or r["baseline_label"].startswith("consolidated")
                        else "; likely among the bills consolidated into this substitute (confirm in the committee report)."),
            LABELS[3]: "; same subject in the other chamber.", LABELS[4]: "; same subject, different design.",
            LABELS[5]: f"; same structure (a {etype.group(1).lower() if etype else 'similar body'}) on a different subject, useful as a model for its provisions.",
            LABELS[6]: "; similar wording only."}[lab]
        rel.append({"id": r["id"], "relationship": lab, "basis": why, "title": ttl, "section": "", "quote": "", "sim": sim if textual else 0})
    rel.sort(key=lambda x: (ORDER.get(x["relationship"], 9), x["id"]))
    laws = []
    cite_secs = {}
    for s in sections(bid):
        for lw in re.findall(r"Republic Act(?: No\.)?\s*(\d{3,5})", s["text"]):
            cite_secs.setdefault(f"RA-{lw}", s["no"])
    for lw in pack.get("laws", [])[:8]:
        cited = lw["law"] in cite_secs
        named = "cited" in (lw.get("why") or "")
        ltitle = lw.get("title", "")
        tmpl = bool(etype and subj and etype.group(1).upper() in ltitle.upper() and not any(w.upper() in ltitle.upper() for w in subj))
        if tmpl and not (cited or named):
            laws.append({"law": lw["law"], "label": LAW_LABELS[3], "title": ltitle, "section": "", "quote": "",
                         "overlap": f"Creates a {etype.group(1).lower()} on a different subject; the bill appears to follow its structure (compare composition, powers and funding)."})
            continue
        laws.append({"law": lw["law"], "label": LAW_LABELS[2] if (cited or named) else LAW_LABELS[1],
                     "overlap": (f"Cited in {sec_ref(bid, cite_secs[lw['law']])}; confirm whether the bill relies on, amends or overlaps with it." if cited
                                 else "Cited in the bill (explanatory note); confirm how the measure relates to it." if named
                                 else "Similar subject by title; confirm whether its functions overlap with the proposed measure."),
                     "title": lw.get("title", ""), "section": "", "quote": ""})
    hist = []
    filed = row.get("date_filed")
    if filed or row.get("author"):
        hist.append(f"{doc} was filed{' on ' + filed if filed else ''}{' by ' + row['author'] if row.get('author') else ''}"
                    + (f"; its current status is {row.get('status_sub', '').lower()} ({row.get('status_group', '').lower()})." if row.get("status_sub") else "."))
    past = [r for r in rel if r["relationship"] == LABELS[0]]
    hist.append("Similar measures were filed in earlier Congresses: " + "; ".join(_short(r["id"]) + f" ({r['id'].split('-')[1]}th)" for r in past[:6]) + "."
                if past else "No measure with a closely matching title or text was found in the 18th or 19th Congress.")
    cps = [r for r in rel if r["relationship"] == LABELS[3]]
    if cps:
        hist.append(f"Counterpart measures in the other chamber: {', '.join(_short(r['id']) for r in cps[:6])}.")
    mg = [r for r in rel if r["relationship"] == LABELS[2]]
    if mg:
        hist.append(f"As a substitute bill, {doc} appears to consolidate {len(mg)} bill{'s' if len(mg) > 1 else ''} on the same subject "
                    f"(e.g., {', '.join(_short(r['id']) for r in mg[:5])}); confirm the list in the committee report.")
    same = [r for r in rel if r["relationship"] == LABELS[1]]
    if same:
        hist.append(f"Near-identical bills filed in the same Congress: {', '.join(_short(r['id']) for r in same[:6])}.")
    for r in pack["related"]:
        fm = (bills.get(r["id"]) or {}).get("front_matter", "")
        m = re.search(r"in substitution of (Senate|House) Bill Nos?\.?\s*([\d\s,and]+)", fm, re.I)
        if m and r["id"].split("-")[0] in ("SB", "HB", "CR"):
            nums = re.sub(r"\s+", " ", m.group(2)).strip(" ,")
            hist.append(f"{_short(r['id'])} was filed in substitution of {m.group(1)} Bill Nos. {nums}.")
            break

    # 3. salient features and related measures (memo style)
    parts = []
    if creates:
        art = ("a " + members + "-member ") if members else ("the " if re.match(r"(Department|Office|Philippine|National)\b", entity or "") else "")
        parts.append(f"{doc} seeks to establish {art}{entity}"
                     + (f" with a {dur} mandate" if dur else "") + (f" to {purpose}" if purpose else "") + ".")
    else:
        parts.append(proposal)
    sup = [s for s in sections(bid) if re.search(r"secretariat|research arm|advisory", s["heading"], re.I)]
    if sup:
        items = [f"{'the ' if not s['heading'].lower().startswith('the ') else ''}{s['heading']} ({sec_ref(bid, s['no']).split(' (')[0]})" for s in sup[:4]]
        parts.append("It would be supported by " + (", ".join(items[:-1]) + ", and " + items[-1] if len(items) > 2 else " and ".join(items)) + ".")
    fq = fiscal(bid, b.get("facts") or {})
    pos = [f for f in fq if f["item"] == "Position"]
    if pos:
        parts.append(f"Under {pos[0]['section']}, the {pos[0].get('heading') or 'head'} would have the rank of {pos[0]['detail']}.")
    ini = next((f for f in fq if f["item"] == "Initial funding"), None)
    if ini:
        if ini.get("amount"):
            sent = f"{ini['section']} provides an initial appropriation of ₱{ini['amount']:,.0f}" + (f", charged against {ini['source']}" if ini["source"] else "")
        elif ini.get("source"):
            sent = f"{ini['section']} provides that the amount necessary for its initial implementation would be charged against {ini['source']}"
        else:
            sent = f"{ini['section']} provides that the amount necessary for its implementation would be included in the annual General Appropriations Act"
        if ini.get("gaa") and (ini.get("amount") or ini.get("source")):
            sent += ", with subsequent requirements included in the annual General Appropriations Act"
        parts.append(sent + ".")
    salient = " ".join(parts)
    cps = sorted([r for r in rel if r["relationship"] == LABELS[3] and r["id"][:2] in ("HB", "SB")], key=lambda r: -r.get("sim", 0))[:2]
    sames = sorted([r for r in rel if r["relationship"] in (LABELS[1], LABELS[2]) and r["id"][:2] in ("HB", "SB")], key=lambda r: -r.get("sim", 0))[:1]
    alongside = cps + sames
    rm = []
    if alongside:
        names = [_doc(r["id"]) for r in alongside]
        rm.append(f"{doc} may be considered alongside {', '.join(names[:-1]) + ' and ' + names[-1] if len(names) > 1 else names[0]}, "
                  + ("which likewise propose " if len(names) > 1 else "which likewise proposes ") + (f"to create a similar {etype.group(1).lower() if etype else 'body'}" if creates else "similar measures") + ".")
    if areas:
        rm.append(f"The measure aligns with the {title_case(areas[0])} priority under the FY 2027 Budget Priorities Framework.")
    # an existing body with a similar mandate in a law the bill relates to (e.g. an oversight committee)
    link = ""
    pw = _find(bid, r"powers|functions")
    for lw in sorted(laws, key=lambda x: x["label"] != LAW_LABELS[2]):
        ls = sections(lw["law"])
        k = next((i for i, x in enumerate(ls) if re.search(r"oversight", x["heading"], re.I)), None)
        if k is None:
            continue
        span = [ls[k]["no"]] + [x["no"] for x in ls[k + 1:k + 3] if re.search(r"powers|functions|report", x["heading"], re.I)]
        rng = f"Sections {span[0]}–{span[-1]}" if len(span) > 1 else f"Section {span[0]}"
        link = (f"the review should assess whether {eshort}'s proposed functions" + (f" under {sec_ref(bid, pw['no'])}" if pw else "")
                + f" address gaps in the mandate of the {title_case(ls[k]['heading'])} under {rng} of {_doc_name_law(lw['law'])}"
                + " and clarify how responsibilities would be assigned between the two bodies.")
        break
    if link and category == "Government organization and mandates":
        rm.append("In view of the government's policy to streamline functions and reduce duplication under the Government Optimization Act "
                  f"(RA No. 12231), {link}")
    elif link:
        rm.append(link[0].upper() + link[1:])
    else:
        rm.append(f"The review should assess {focus}.")
    checks = inconsistencies(bid)
    return {"target": bid, "entity_proposed": entity, "source": "rules", "proposal": proposal, "alignment": align,
            "legislative_history": hist, "related": rel, "existing_law_overlaps": laws, "salient_features": salient,
            "related_measures_policy": " ".join(rm), "fiscal_requirements": fq, "reviewer_checks": checks, "gaps": []}


PACK_WORDS = re.compile(r"\b(evidence )?pack\b|\bcorpus\b", re.I)


def normalize(out, bid, draft):
    """Fill the version-3 structure from an AI output (any version), using the rule draft for missing parts."""
    if not out:
        return draft
    o = dict(out)
    o.setdefault("source", "ai")
    for k in ("proposal", "alignment", "legislative_history", "salient_features", "related_measures_policy", "fiscal_requirements"):
        if not o.get(k):
            o[k] = draft.get(k)
    bills, _ = load()
    titles = {r["id"]: r.get("title", "") for r in draft.get("related", [])}
    o["related"] = [dict(r, relationship=display_label(r.get("relationship", ""), bid, r.get("id")),
                         title=r.get("title") or (bills.get(r.get("id")) or {}).get("title") or titles.get(r.get("id"), ""))
                    for r in out.get("related", [])]
    ltitles = {x["law"]: x.get("title", "") for x in draft.get("existing_law_overlaps", [])}
    o["existing_law_overlaps"] = [dict(x, label=LAW_LABELS[1] if x.get("label") not in LAW_LABELS else x["label"],
                                       title=x.get("title") or (bills.get(x.get("law")) or {}).get("title", "") or ltitles.get(x.get("law"), ""))
                                  for x in out.get("existing_law_overlaps", [])]
    rc = list(o.get("reviewer_checks") or []) + [g for g in out.get("gaps", []) if not PACK_WORDS.search(g)]
    o["reviewer_checks"] = list(dict.fromkeys(draft.get("reviewer_checks", []) + rc))
    return o


def saved_ai(bid):
    """A TrAIce run saved with ActCheck itself (data/agent_runs/<bill>/traice.json), e.g. one run by Claude offline."""
    p = RUNS / bid / "traice.json"
    try:
        return json.loads(p.read_text()) if p.exists() else None
    except Exception:
        return None


CHECKLIST = [
    "The proposal, salient features and fiscal requirements match the bill (checked against the PDF or full text).",
    "The legislative history and related bills are complete and correctly grouped (checked against House and Senate records).",
    "The related laws and overlapping mandates are confirmed.",
    "Inconsistent provisions, typographical and grammatical errors are noted.",
    "The TrAIce output above is correct and will be added to the memo.",
]
