"""CompAIre (Agent 2), version 3: what is materially different in this bill, and is it a valid design?

Building on TrAIce's salient features and related measures, CompAIre compares the bill's major provisions, section by
section, with the most useful alternative in related measures (chosen per provision: where the alternative differs, not
where it repeats), and recommends for each provision one of four design options:
    Retain provision · Adapt alternative · Adapt alternative with revisions · Remove provision
with the reason, the trade-offs and the gaps to check. It also notes possible duplication of existing functions and the
likely cost direction of each difference; both feed ApprAIsal (Step 3) and are reviewed there, not here.

Main output: memo Part IV (Comments and Recommendations), only for provisions that need a decision
(adapt, adapt with revisions, remove); provisions recommended for retention are left out.

Rules-only draft (no AI): rule_draft(). Claude's run: build_messages() + check_output(); saved runs in
data/agent_runs/<bill>/compaire.json are shown on the site as "Prepared by CompAIre (Claude)".
"""
import json
import re
from pathlib import Path

from pipeline.compare import load, align
from agents import traice

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "data" / "agent_runs"
PROMPT_VERSION = "v3.1"
RECS = ["Retain provision", "Adapt alternative", "Adapt alternative with revisions", "Remove provision"]
DECISION = RECS[1:]
AREAS = [  # (heading pattern, area name used in the table and in the memo subheading)
    (r"declaration|policy|objective|purpose|mandate", "Mandate and objectives"),
    (r"creat|establish", "Creation and nature of the body"),
    (r"composition|membership|members", "Composition"),
    (r"executive director|secretary|head|chair|commissioner", "Head and key positions"),
    (r"secretariat|staff|personnel|plantilla", "Secretariat and staffing"),
    (r"research arm|research", "Research support"),
    (r"advisory|council|committee", "Advisory and support bodies"),
    (r"duration|term|sunset|life", "Duration"),
    (r"powers|functions", "Powers and functions"),
    (r"organi[sz]ational|structure|offices|regional|attach", "Organization and attachment"),
    (r"transfer|abolish|abolition|absorb|merg", "Transfer or abolition of offices"),
    (r"appropriation|fund", "Funding"),
    (r"report", "Reporting and oversight"),
]
SKIP = r"short title|definition|separability|repeal|effectivity|implementing rules|transitory|construction|interpretation"
TRADEOFFS = {
    "Composition": "A larger body broadens representation but adds coordination effort and allowances.",
    "Head and key positions": "A higher rank helps recruitment and authority but raises personnel cost.",
    "Secretariat and staffing": "A dedicated secretariat improves continuity but adds positions; detailed staff cost less but may lack independence.",
    "Funding": "A stated amount aids planning and accountability; an open amount gives flexibility but makes the cost harder to estimate.",
    "Duration": "A fixed term limits cost and forces results; a longer term allows deeper work at higher cost.",
    "Powers and functions": "Broader powers support the mandate but raise the risk of overlap with existing agencies.",
    "Advisory and support bodies": "More support bodies widen expertise but add meetings, honoraria and coordination.",
    "Research support": "An existing research institution lowers cost but competes with its other work.",
    "Mandate and objectives": "A wider mandate covers more of the problem but is harder to deliver and to measure.",
    "Creation and nature of the body": "A new body gives focus but adds to the number of government entities.",
    "Organization and attachment": "Attachment to an existing agency eases support and oversight but may reduce independence.",
    "Transfer or abolition of offices": "Transfers avoid duplication but disrupt existing staff and programs during transition.",
    "Reporting and oversight": "More reporting improves accountability but adds workload.",
}


def area_of(heading):
    if re.search(SKIP, heading, re.I):
        return None
    for rx, name in AREAS:
        if re.search(rx, heading, re.I):
            return name
    return None


def facts(text):
    """Simple facts from a section's text, used to describe differences (no AI)."""
    t = " ".join(text.split())
    f = {}
    m = re.findall(r"\b(?:composed of|consist(?:ing|s)? of)\s+(?:the following\s+)?(\w+(?:[- ]\w+)?)\s*\((\d+)\)\s*members", t, re.I)
    if m:
        f["members"] = int(m[0][1])
    sg = re.findall(r"Salary Grade\s*(\d{2})", t, re.I)
    if sg:
        f["salary_grade"] = sorted({int(x) for x in sg})
    amt = re.findall(r"(?:P|₱|PHP|Php)\s?([\d,]{5,}(?:\.\d+)?)", t)
    if amt:
        f["amount"] = sorted({round(float(a.replace(",", ""))) for a in amt})
    yrs = re.findall(r"\b(\w+)\s*\((\d+)\)\s*years?\b", t, re.I)
    if yrs:
        f["years"] = sorted({int(y[1]) for y in yrs})
    if re.search(r"General Appropriations Act", t, re.I):
        f.setdefault("funding", []).append("General Appropriations Act")
    if re.search(r"appropriations of the (Senate|House)", t, re.I):
        f.setdefault("funding", []).append("congressional appropriations")
    if re.search(r"amount necessary", t, re.I):
        f.setdefault("funding", []).append("amount necessary (no figure)")
    att = re.search(r"attached to the ([A-Z][\w ,]{3,60}?)(?:\s+for|\.|,)", t)
    if att:
        f["attached_to"] = att.group(1).strip()
    return f


def describe(fa, fb):
    """What differs between two fact sets: (table phrase, memo phrase) pairs."""
    out = []
    money = lambda v: ", ".join(f"PHP {x:,}" for x in v)
    plain = lambda v: ", ".join(map(str, v)) if isinstance(v, list) else str(v)
    spec = {"members": ("members", lambda v: f"{plain(v)} members"),
            "salary_grade": ("salary grade", lambda v: f"Salary Grade {plain(v)}"),
            "years": ("years", lambda v: f"a period of {plain(v)} year{'' if v == [1] else 's'}"),
            "amount": ("amount", lambda v: f"an amount of {money(v)}")}
    for k, (lab, memo) in spec.items():
        a, b = fa.get(k), fb.get(k)
        if b and a != b:
            fmt = money if k == "amount" else plain
            out.append((f"{lab}: {fmt(b)} (this bill: {fmt(a) if a else 'not stated'})", memo(b)))
    if fb.get("funding") and set(fb["funding"]) != set(fa.get("funding", [])):
        out.append((f"funding: {', '.join(fb['funding'])} (this bill: {', '.join(fa.get('funding', [])) or 'not stated'})",
                    "funding from " + " and ".join(x for x in fb["funding"] if "no figure" not in x) if any("no figure" not in x for x in fb["funding"])
                    else "the amount necessary, without a figure"))
    if fb.get("attached_to") and fb.get("attached_to") != fa.get("attached_to"):
        out.append((f"attached to the {fb['attached_to']}", f"attachment to the {fb['attached_to']}"))
    return out


def comparators(bid, t_out=None, k=4):
    """Related bills with full text that can offer an alternative design (near-identical copies give none)."""
    bills, secs = load()
    rel = (t_out or {}).get("related") or []
    order = {traice.LABELS[3]: 0, "Senate version": 0, "House version": 0, traice.LABELS[4]: 1, traice.LABELS[2]: 2, traice.LABELS[0]: 3}
    ids = [r["id"] for r in sorted(rel, key=lambda r: order.get(r.get("relationship"), 5))
           if r.get("id") in secs and r.get("relationship") != traice.LABELS[1] and r.get("id") != bid]
    if not ids:
        from pipeline.compare import related_bills
        ids = [r["id"] for r in related_bills(bid, top=10) if r["id"] in secs and (r.get("similarity") or 0) < 0.9]
    ids = list(dict.fromkeys(ids))
    if any(i[:2] in ("HB", "SB") for i in ids):
        ids = [i for i in ids if i[:2] in ("HB", "SB")]
    return ids[:k]


def rows_for(bid, comps):
    """One row per major provision of the bill: the comparator section that differs most while covering the same matter."""
    bills, secs = load()
    aligned = {c: {r["a_section"]: r for r in align(bid, c) if r["a_section"]} for c in comps}
    rows = []
    for s in secs.get(bid, []):
        area = area_of(s["heading"])
        if not area:
            continue
        best = None
        for c in comps:
            r = aligned[c].get(s["id"])
            if not r or not r["b_section"]:
                continue
            cs = next((x for x in secs[c] if x["id"] == r["b_section"]), None)
            diff = describe(facts(s["text"]), facts(cs["text"])) if cs else []
            score = (len(diff), 1 - (r["similarity"] or 0))          # most fact differences first, then least similar
            if r["similarity"] is not None and r["similarity"] < 0.9 and (best is None or score > best[0]):
                best = (score, c, r, cs, diff)
        rows.append({"section": s["id"], "no": s["no"], "heading": s["heading"], "area": area, "text": s["text"], "best": best})
    return rows


def _name(i):
    p = str(i).split("-")
    return traice._doc(i) if p[0] in ("HB", "SB") else traice._short(i).strip()


def rule_draft(bid, t_out=None, pack=None):
    """CompAIre's draft by code (no AI): rows of the Substantial Differences and Design Options table and memo Part IV."""
    bills, secs = load()
    b = bills.get(bid) or {}
    doc = traice._doc(bid)
    comps = comparators(bid, t_out)
    note = " ".join((b.get("explanatory_note") or "").split())
    sents = [x for x in re.split(r"(?<=[.!?])\s+", note) if 60 < len(x) < 400 and not re.search(r"approval of this|earnest|immediate", x, re.I)]
    key = r"problem|lack|need|challenge|declin|low |weak|gap|fragment|poor|vulnerab|insufficien|inadequa|absence|limited|not been"
    sents = sorted(sents, key=lambda x: (not re.search(key, x, re.I), sents.index(x)))
    problem = " ".join(sents[:2]) if sents else (t_out or {}).get("proposal", "")
    overlaps = [x for x in (t_out or {}).get("existing_law_overlaps", []) if x.get("label") == traice.LAW_LABELS[1]]
    out_rows, memo, dup, cost = [], [], [], []
    for r in rows_for(bid, comps):
        ref = traice.sec_ref(bid, r["no"])
        gaps = []
        if r["best"]:
            _, c, al, cs, diff = r["best"]
            cref = f"Section {cs['no']} ({cs['heading']})"
            differences = (f"{_name(c)}, {cref}: " + ("; ".join(d[0] for d in diff) if diff else
                           f"same matter with different terms ({al['similarity']:.0%} wording in common)") + ".")
            if r["area"] == "Funding" and diff:
                rec, why = RECS[2], f"{_name(c)} sets a clearer funding basis; adapt it, with the amount to be validated in ApprAIsal."
            elif diff:
                rec, why = RECS[0], "Differences noted; ActCheck's rules do not judge design merit. Decide after reading both provisions."
            else:
                rec, why = RECS[0], "The alternative words the same matter differently; no material design choice found by the rules."
            if bills.get(c, {}).get("text_source") == "ocr":
                gaps.append(f"{_name(c)} text recognized from a scanned PDF; confirm the wording")
            comparator = {"id": c, "title": bills.get(c, {}).get("title", ""), "section": cs["id"]}
        else:
            differences = "No related measure offers a different design for this provision."
            rec, why = RECS[0], "No alternative found in the related measures."
            comparator = None
        if r["area"] == "Powers and functions" and overlaps:
            o = overlaps[0]
            gaps.append(f"Possible duplication with {traice._doc_name_law(o['law'])}: {o.get('overlap', '').rstrip('.')}")
            dup.append({"function": f"{ref}", "existing": traice._doc_name_law(o["law"]), "note": o.get("overlap", "")})
        memo_cmp = (f"In comparison, {_name(r['best'][1])}, in Section {r['best'][3]['no']} ({r['best'][3]['heading']}), provides for "
                    + ", ".join(d[1] for d in r["best"][4]) + ".") if r["best"] and r["best"][4] else ""
        out_rows.append({"area": r["area"], "section_ref": ref, "target_section": r["section"], "comparator": comparator, "_memo_cmp": memo_cmp,
                         "differences": differences, "recommendation": rec, "why": why,
                         "tradeoffs": TRADEOFFS.get(r["area"], ""), "gap": "; ".join(gaps)})
        if r["best"] and r["best"][4]:
            cost.append({"item": ref, "direction": "unclear", "why": "; ".join(d[0] for d in r["best"][4])})
    # memo Part IV: provisions that need a decision, plus provisions with fact differences for the reviewer to settle
    n = 0
    for row in out_rows:
        if row["recommendation"] in DECISION or (row["comparator"] and "(this bill:" in row["differences"]):
            n += 1
            gist = traice._gist(next(x["text"] for x in secs[bid] if x["id"] == row["target_section"]),
                                next(x["heading"] for x in secs[bid] if x["id"] == row["target_section"]))
            para = f"4.{n} {row['section_ref']} of {doc} {gist.rstrip('.…')}."
            if row.get("_memo_cmp"):
                para += " " + row["_memo_cmp"]
            para += (f" In this regard, we recommend that the provision be revised along the lines of {_name(row['comparator']['id'])}, "
                     "subject to the validation of the cost by ApprAIsal." if row["recommendation"] == RECS[2] else
                     " The reviewer may consider whether to retain the provision or adapt the alternative.")
            memo.append({"heading": f"On the {row['area'][0].lower() + row['area'][1:]}", "paragraphs": [para]})
    for row in out_rows:
        row.pop("_memo_cmp", None)
    return {"target": bid, "source": "rules", "problem": problem, "comparators": comps, "rows": out_rows,
            "duplications": dup, "cost_notes": cost, "memo_part": memo,
            "reviewer_checks": [r["gap"] for r in out_rows if r["gap"]]}


def memo_text(out):
    """Memo Part IV as editable text: a subheading line per topic, then numbered paragraphs."""
    lines = []
    for m in out.get("memo_part", []):
        lines.append(m.get("heading", ""))
        lines += m.get("paragraphs", [])
        lines.append("")
    return "\n".join(lines).strip()


def saved_ai(bid):
    p = RUNS / bid / "compaire.json"
    try:
        return json.loads(p.read_text()) if p.exists() else None
    except Exception:
        return None


def normalize(out, bid, draft):
    if not out:
        return draft
    o = dict(out)
    o.setdefault("source", "ai")
    bills, _ = load()
    for r in o.get("rows", []):
        c = r.get("comparator")
        if c and not c.get("title"):
            c["title"] = (bills.get(c.get("id")) or {}).get("title", "")
    o["reviewer_checks"] = list(dict.fromkeys((o.get("reviewer_checks") or []) + [r["gap"] for r in o.get("rows", []) if r.get("gap")]))
    for k in ("problem", "duplications", "cost_notes"):
        o.setdefault(k, draft.get(k))
    return o


def grade(bid, out, checks=None):
    from agents import grading
    b = load()[0].get(bid) or {}
    kind = out.get("source", "ai")
    alt = [r for r in out.get("rows", []) if r.get("comparator")]
    full = sum(1 for r in alt if r["comparator"].get("section") and not str(r["comparator"]["section"]).startswith(("meta:", "law:")))
    return grading.finish([
        grading.text_test(b.get("text_source")),
        grading.prep_test(kind, checks),
        grading.share_test(full, len(alt), "design comparisons made against a comparator's full section",
                           "No related measure with a full text offered an alternative design"),
        grading.open_test(len(out.get("reviewer_checks") or []), "the gaps column"),
    ], kind)


# ---------------- Claude's run ----------------
def build_messages(bid, t_out=None):
    from agents import llm
    bills, secs = load()
    draft = rule_draft(bid, t_out)
    comps = draft["comparators"]
    tgt = "\n".join(f"[{s['id']}] {s['heading']}: {' '.join(s['text'].split())[:1800]}" for s in secs.get(bid, []))
    alt_blocks = []
    for c in comps:
        rows = {r["a_section"]: r for r in align(bid, c) if r["a_section"] and r["b_section"]}
        used = {r["b_section"] for r in rows.values() if (r["similarity"] or 0) < 0.9}
        only_b = [r["b_section"] for r in align(bid, c) if r["status"] == "only in B"]
        blk = [f"[{s['id']}] {s['heading']}: {' '.join(s['text'].split())[:1400]}" for s in secs[c] if s["id"] in used | set(only_b)]
        alt_blocks.append(f"COMPARATOR {c} ({bills[c]['label']}, {bills[c]['congress']}th Congress): {bills[c]['title'][:300]}\n" + "\n".join(blk))
    t_ctx = {k: (t_out or {}).get(k) for k in ("proposal", "alignment", "salient_features", "related_measures_policy")}
    t_ctx["related"] = [{k: r.get(k) for k in ("id", "relationship", "basis")} for r in (t_out or {}).get("related", [])]
    t_ctx["related_laws"] = [{k: x.get(k) for k in ("law", "label", "overlap")} for x in (t_out or {}).get("existing_law_overlaps", [])]
    keep = {k: draft[k] for k in ("problem", "rows")}
    for r in keep["rows"]:
        r.pop("why", None)
    user = (f"TARGET: {bid} ({bills[bid]['label']}, {bills[bid]['congress']}th Congress): {bills[bid]['title']}\n\n"
            f"TRAICE OUTPUT (Step 1, reviewed by the analyst): {json.dumps(t_ctx, ensure_ascii=False)}\n\n"
            f"ACTCHECK DRAFT (made by code, no AI; improve it): {json.dumps(keep, ensure_ascii=False)}\n\n"
            f"EXPLANATORY NOTE (cite as {bid}:note):\n{(bills[bid].get('explanatory_note') or '')[:2500]}\n\n"
            f"TARGET SECTIONS:\n{tgt}\n\n" + "\n\n".join(alt_blocks))
    return llm.prompt("p2_compaire"), user, draft


def check_output(out):
    from agents.verify import check_citations, quote_found
    bills, _ = load()
    claims = []
    for r in out.get("rows", []):
        if r.get("target_section") and r.get("target_quote"):
            claims.append({"claim": r.get("section_ref", ""), "section": r["target_section"], "quote": r["target_quote"]})
        c = r.get("comparator") or {}
        if c.get("section") and c.get("quote"):
            claims.append({"claim": r.get("differences", ""), "section": c["section"], "quote": c["quote"]})
    for d in out.get("duplications", []):
        if d.get("section") and d.get("quote"):
            claims.append({"claim": d.get("note", ""), "section": d["section"], "quote": d["quote"]})
    if out.get("problem_quote"):
        claims.append({"claim": "problem", "section": f"{out.get('target')}:note", "quote": out["problem_quote"]})
    checks = []
    for c in claims:
        if c["section"].endswith(":note"):
            b = c["section"].rsplit(":", 1)[0]
            ok = b in bills and quote_found(c["quote"], bills[b].get("explanatory_note", ""))
            checks.append({**c, "check": "verified" if ok else "quote not found in section"})
        else:
            checks += check_citations([c])
    areas = {r.get("area") for r in out.get("rows", [])}
    for x in out.get("self_critique") or []:
        if x.get("verdict") not in VERDICTS or x.get("area") not in areas:
            checks.append({"claim": "self-critique", "section": "", "quote": str(x.get("area")),
                           "check": "self-critique must name a row of the table and use stands, weakened or reversed"})
    for r in out.get("rows", []):
        if r.get("recommendation") not in RECS:
            checks.append({"claim": r.get("section_ref", ""), "section": r.get("target_section", ""), "quote": "",
                           "check": f"unknown recommendation: {r.get('recommendation')}"})
    return checks


def run_agent(bid, t_out=None):
    from agents import llm
    system, user, draft = build_messages(bid, t_out)
    text, meta = llm.call("compaire", system, user, max_tokens=8000)
    out = json.loads(text[text.find("{"): text.rfind("}") + 1])
    return {"output": out, "checks": check_output(out), "meta": meta}



# ---------------- /attack: CompAIre argues against its own design ----------------
VERDICTS = ("stands", "weakened", "reversed")


def _words(t):
    return {w for w in re.findall(r"[a-z]{4,}", str(t or "").lower())}


def flattering(out):
    """Signs of a flattering self-critique: every verdict 'stands', objections that repeat the row's own reason,
    objections called minor, or rows left unattacked. Returns the reasons found."""
    crit = out.get("self_critique") or []
    rows = {r.get("area"): r for r in out.get("rows", [])}
    why = []
    if not crit:
        return why
    if len(crit) >= 3 and all(x.get("verdict") == "stands" for x in crit):
        why.append("every objection was judged not to change the recommendation")
    echo = [x["area"] for x in crit if x.get("area") in rows and _words(x.get("objection")) and
            len(_words(x.get("objection")) & _words(rows[x["area"]].get("why"))) / len(_words(x.get("objection"))) >= 0.6]
    if echo:
        why.append("the objection repeats the recommendation's own reason (" + ", ".join(echo) + ")")
    if any(re.search(r"\bminor\b|\bnegligible\b|\bonly a small\b", x.get("objection", ""), re.I) for x in crit):
        why.append("an objection is dismissed as minor")
    missing = [a for a in rows if a not in {x.get("area") for x in crit}]
    if missing:
        why.append("rows not attacked: " + ", ".join(missing))
    return why


def critique_points(out):
    """Checklist lines: the theory of change, the self-critique per row, and any sign of a flattering critique."""
    pts = []
    toc = out.get("theory_of_change") or {}
    if toc:
        pts.append("Theory of change: " + "; ".join(f"{k.replace('_', ' ')}: {v.rstrip('.')}" for k, v in
                                                  (("problem", toc.get("problem")), ("mechanism", toc.get("mechanism")),
                                                   ("outcome", toc.get("outcome")), ("weakest assumption", toc.get("weakest_assumption"))) if v) + ".")
    crit = out.get("self_critique") or []
    if not crit:
        pts.append("Self-critique: not done for this output (draft prepared by code); test each recommendation against its strongest objection.")
    for x in crit:
        pts.append(f"Self-critique ({x.get('area')}): {x.get('objection', '').rstrip('.')}. Verdict: {x.get('verdict')}"
                   + (f", on condition that {x['condition'][:1].lower() + x['condition'][1:].rstrip('.')}" if x.get("condition") else "") + ".")
    f = flattering(out)
    if f:
        pts.append("Check for a flattering self-critique: " + "; ".join(f) + ".")
    return pts
