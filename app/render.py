"""Concise displays of each agent's output for the review workspace.

Lead with the finding, keep tables short (one line per row), and put the evidence quotes in an
expander so nothing is lost but the page stays readable.
"""
import re
from html import escape

import pandas as pd
import streamlit as st

import ui


def short(s, n=170):
    s = " ".join(str(s or "").split())
    return s if len(s) <= n else s[: n - 1].rsplit(" ", 1)[0] + "…"


def label(bid):
    parts = str(bid).split("-")
    if len(parts) == 3 and parts[0] in ("HB", "SB"):
        return f"{parts[0]} {parts[2]} ({parts[1]}th)"
    return str(bid).replace("-", " ", 1)


def verification(checks):
    if not checks:
        return
    ok = sum(1 for c in checks if c.get("check") == "verified")
    bad = [c for c in checks if c.get("check") != "verified"]
    ui.notice(
        f"<b>{ok} of {len(checks)}</b> citations verified against the source text."
        + ("" if not bad else f" <b>{len(bad)}</b> need checking: open <i>Evidence quotes</i> below."), "" if not bad else "red")


def quotes(rows, key):
    """rows: dicts with section, quote and optional check."""
    with st.expander("Evidence quotes"):
        df = pd.DataFrame([{"Source": r.get("section", ""), "Quote": r.get("quote", ""), "Check": r.get("check", "")} for r in rows])
        st.dataframe(df, use_container_width=True, hide_index=True, key=key)


def _doc_name(i):
    from agents import traice
    parts = str(i).split("-")
    if parts[0] in ("HB", "SB") and len(parts) == 3:
        return traice._doc(i) + f" ({parts[1]}th)"
    if parts[0] in ("RA", "PD", "EO", "CA", "BP") and len(parts) >= 2:
        return f"{'RA' if parts[0] == 'RA' else parts[0]} No. {'-'.join(parts[1:])}"
    return traice._short(i).strip()


def _grouped(rows, group_key, cols, cls):
    """A table whose first column (the relationship) spans the rows of its group."""
    head = "".join(f"<th>{escape(h)}</th>" for h in cols)
    body, groups = "", {}
    for r in rows:
        groups.setdefault(r[group_key], []).append(r)
    for g, items in groups.items():
        for j, r in enumerate(items):
            first = (f'<td rowspan="{len(items)}" class="grp"><span class="ac-badge navy">{escape(g)}</span>'
                     f'<div class="n">{len(items)} item{"s" if len(items) > 1 else ""}</div></td>') if j == 0 else ""
            body += "<tr>" + first + "".join(f"<td>{c}</td>" for c in r["cells"]) + "</tr>"
    ui.html(f'<table class="ac-tbl grp {cls}"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table>')


def _name_title(i, title):
    from pipeline.compare import load
    full = (load()[0].get(i) or {}).get("title") or ""
    t = " ".join(str(full if len(full) > len(str(title or "")) else title or "").split())
    return (f'<b class="m">{escape(_doc_name(i))}</b>'
            + (f'<div class="ttl">{escape(short(t, 330))}</div>' if t else '<div class="ttl">Title not available; listing only.</div>'))


def trace(bid, out, checks=None):
    """Step 1: TrAIce (version 3): policy context, legislative history, related bills and laws, fiscal requirements."""
    from agents import traice
    src = out.get("source", "ai")
    ok = sum(1 for c in (checks or []) if c.get("check") == "verified")
    if src == "rules":
        ui.badges([("Draft prepared by ActCheck's rules (no AI)", "gold")])
    elif src == "ai-v2":
        ui.badges([("Related bills and laws labelled by TrAIce (Claude, earlier version); other parts drafted by ActCheck's rules", "gold")]
                  + ([(f"{ok} of {len(checks)} cited sections verified against the text", "green" if ok == len(checks) else "red")] if checks else []))
    else:
        ui.badges([("Prepared by TrAIce (Claude)", "navy")]
                  + ([(f"{ok} of {len(checks)} cited sections verified against the text", "green" if ok == len(checks) else "red")] if checks else []))
    ui.html('<div class="ac-sec">Policy context</div>'
            f'<div class="ac-out"><p>{escape(out.get("proposal", ""))}</p><p>{escape(out.get("alignment", ""))}</p></div>')
    hist = out.get("legislative_history") or []
    if hist:
        ui.html('<div class="ac-sec">Legislative history</div><div class="ac-out"><ul>'
                + "".join(f"<li>{escape(h)}</li>" for h in hist) + "</ul></div>")
    rel = [r for r in out.get("related", []) if r.get("id") != bid and r.get("relationship") not in (traice.LABELS[5], traice.LABELS[6])]
    if rel:
        order = {lab: i for i, lab in enumerate(traice.LABELS + ["Senate version", "House version"])}
        order["Senate version"] = order["House version"] = traice.ORDER[traice.LABELS[3]]
        rel = sorted(rel, key=lambda r: (order.get(r.get("relationship"), 9), r.get("id", "")))
        ui.html('<div class="ac-sec">Related Bills</div>')
        _grouped([{"g": r.get("relationship") or "Not classified",
                   "cells": [_name_title(r.get("id"), r.get("title")), escape(short(r.get("basis"), 220))]} for r in rel],
                 "g", ["Relationship", "Bill number and title", "Why"], "relb")
    laws = [x for x in out.get("existing_law_overlaps", []) if x.get("label") != traice.LAW_LABELS[3]]   # content, not format
    if laws:
        lo = {lab: i for i, lab in enumerate(traice.LAW_LABELS)}
        laws = sorted(laws, key=lambda x: (lo.get(x.get("label"), 9), x.get("law", "")))
        ui.html('<div class="ac-sec">Related Laws</div>')
        _grouped([{"g": x.get("label") or traice.LAW_LABELS[1],
                   "cells": [_name_title(x.get("law"), x.get("title")), escape(short(x.get("overlap"), 240))]} for x in laws],
                 "g", ["Relationship", "Law and title", "Overlap"], "relb")


def fiscal_table(fq):
    """The bill's fiscal requirements, identified by TrAIce, shown with ApprAIsal's cost work."""
    ui.html('<div class="ac-sec">Fiscal requirements (identified by TrAIce)</div>')
    if fq:
        ui.table(["Item", "Requirement", "Provision"],
                 [[escape(f.get("item", "")), escape(f.get("detail", "")), escape(f.get("section", ""))] for f in fq], cls="fisc")
    else:
        ui.html('<div class="ac-out"><p>No appropriations clause, position or funding provision was identified; '
                'confirm against the full text.</p></div>')


def memo_html(text):
    """Memo paragraphs; lines starting 'a.', 'b.' ... become a lettered list."""
    out, items = [], []
    for line in [x.strip() for x in str(text or "").split("\n") if x.strip()]:
        m = re.match(r"^([a-z])[.)]\s+(.*)", line)
        if m:
            items.append(f'<li><span class="ltr">{m.group(1)}.</span> {escape(m.group(2))}</li>')
            continue
        if items:
            out.append('<ol class="ac-ltr">' + "".join(items) + "</ol>")
            items = []
        out.append(f"<p>{escape(line)}</p>")
    if items:
        out.append('<ol class="ac-ltr">' + "".join(items) + "</ol>")
    return "".join(out)


def trace_baseline(pack):
    """Kept for reference: the raw similarity list before any drafting."""
    ui.table(["Bill", "Wording in common", "Likely relationship", "Title"],
             [[escape(label(r["id"])), f"{r['similarity']:.0%}" if r.get("similarity") is not None else "–",
               escape(r.get("baseline_label", "")), escape(short(r.get("title"), 110))] for r in pack["related"][:10]], mono_cols=(0, 1))


FISCAL = {"likely raises cost": "red", "likely lowers cost": "green", "no cost effect": "", "unclear": "gold"}


def compare(out, checks=None, baseline_md=None):
    """Step 2: CompAIre."""
    if not out:
        ui.notice("<b>Before any AI is used:</b> ActCheck's own section-by-section comparison with the related bill.", "navy")
        with st.expander("Show the comparison", expanded=True):
            st.markdown(baseline_md or "")
        return
    ui.badges([(f"Verdict: {out.get('verdict', '')}", "navy"), (f"Compared with {label(out.get('reference'))}", "")])
    pd_ = out.get("problem_diagnosis") or {}
    if pd_.get("problem"):
        ui.html(f'<div class="ac-out"><p><b>Problem the bill addresses.</b> {escape(short(pd_["problem"], 600))}</p></div>')
    cites = (checks or {}).get("citations") if isinstance(checks, dict) else checks
    verification(cites)
    diffs = out.get("differences", [])
    if diffs:
        ui.html(f"<p><b>Substantial differences ({len(diffs)})</b></p>")
        ui.table(["Area", "Cost effect", "What changed"],
                 [[escape(d.get("category", "").capitalize()),
                   f'<span class="ac-badge {FISCAL.get(d.get("fiscal_direction", ""), "")}">{escape(d.get("fiscal_direction", ""))}</span>',
                   escape(short(d.get("description"), 230))] for d in diffs])
    opts = out.get("design_options", [])
    if opts:
        ui.html(f"<p><b>Design options seen in related bills ({len(opts)})</b></p>")
        ui.table(["Option", "Found in", "Trade-off"], [[escape(short(o.get("option"), 120)), escape(label(o.get("found_in"))),
                                                     escape(short(o.get("trade_off"), 160))] for o in opts], mono_cols=(1,))
    rows = [dict(section=d.get("target_section"), quote=d.get("target_quote")) for d in diffs] + \
           [dict(section=d.get("reference_section"), quote=d.get("reference_quote")) for d in diffs]
    quotes(cites or rows, "q_compare")
    extra = out.get("baseline_corrections", []), out.get("gaps", [])
    if any(extra):
        with st.expander("Where the agent corrected ActCheck's own section matching, and open gaps"):
            for c in extra[0]:
                st.markdown(f"- **{c.get('target_section')} ↔ {c.get('reference_section')}**: {c.get('note')}")
            for g in extra[1]:
                st.markdown(f"- Gap: {g}")


REC_COLOR = {"Retain provision": "green", "Adapt alternative": "navy", "Adapt alternative with revisions": "gold", "Remove provision": "red"}


def compaire(bid, out, checks=None):
    """Step 2: CompAIre (version 3): the problem, then Substantial Differences and Design Options (no quotes shown)."""
    src = out.get("source", "ai")
    ok = sum(1 for c in (checks or []) if c.get("check") == "verified")
    if src == "rules":
        ui.badges([("Draft prepared by ActCheck's rules (no AI)", "gold")])
    else:
        ui.badges([("Prepared by CompAIre (Claude)", "navy")]
                  + ([(f"{ok} of {len(checks)} cited sections verified against the text", "green" if ok == len(checks) else "red")] if checks else []))
    ui.html('<div class="ac-sec">What the bill aims to address</div>'
            f'<div class="ac-out"><p>{escape(out.get("problem") or "Not stated in the bill.")}</p></div>')
    rows = out.get("rows") or []
    if not rows:
        return
    ui.html('<div class="ac-sec">Substantial Differences and Design Options</div>')
    groups = {}
    for r in rows:
        groups.setdefault((r.get("area"), r.get("section_ref")), []).append(r)
    head = "".join(f"<th>{h}</th>" for h in ["Section / area", "Related measure", "Major differences", "Recommended option", "Trade-offs", "Gaps to check"])
    body = ""
    for (area, ref), items in groups.items():
        for j, r in enumerate(items):
            first = (f'<td rowspan="{len(items)}" class="grp"><b>{escape(ref or "")}</b><div class="n">{escape(area or "")}</div></td>') if j == 0 else ""
            c = r.get("comparator") or {}
            rel = (f'<b class="m">{escape(_doc_name(c["id"]))}</b><div class="ttl">{escape(short(c.get("title", ""), 90))}</div>'
                   if c.get("id") else '<span class="ttl">None offers a different design</span>')
            rec = r.get("recommendation", "")
            body += (f"<tr>{first}<td>{rel}</td><td>{escape(r.get('differences', ''))}</td>"
                     f'<td><span class="ac-badge {REC_COLOR.get(rec, "")}">{escape(rec)}</span><div class="why">{escape(r.get("why", ""))}</div></td>'
                     f"<td>{escape(r.get('tradeoffs', ''))}</td><td>{escape(r.get('gap', '') or '–')}</td></tr>")
    ui.html(f'<div class="ac-wide"><table class="ac-tbl grp cmp"><thead><tr>{head}</tr></thead><tbody>{body}</tbody></table></div>')


def memo3_html(text):
    """Memo Part IV: 'On the ...' lines as italic bold subheadings, '3.1 ...' paragraphs with hanging numbers."""
    out = []
    for line in [x.strip() for x in str(text or "").split("\n") if x.strip()]:
        m = re.match(r"^(\d+\.\d+)\s+(.*)", line)
        if m:
            out.append(f'<div class="np"><span class="no">{m.group(1)}</span><p>{escape(m.group(2))}</p></div>')
        elif len(line) < 110 and not line.endswith("."):
            out.append(f'<div class="oh">{escape(line)}</div>')
        else:
            out.append(f"<p>{escape(line)}</p>")
    return "".join(out)


def compaire_feeds(out):
    """What CompAIre passes to ApprAIsal: possible duplication of functions and cost directions."""
    dup, cost = out.get("duplications") or [], out.get("cost_notes") or []
    if dup:
        ui.html('<div class="ac-sec">Possible duplication of functions (identified by CompAIre)</div>')
        ui.table(["Provision of the bill", "Existing office or body", "Note"],
                 [[escape(d.get("function", "")), escape(d.get("existing", "")), escape(d.get("note", ""))] for d in dup], cls="fisc")
    if cost:
        ui.html('<div class="ac-sec">Cost implications of the differences (identified by CompAIre)</div>')
        ui.table(["Provision", "Likely effect", "Why"],
                 [[escape(c.get("item", "")), escape(c.get("direction", "")), escape(c.get("why", ""))] for c in cost], cls="fisc")


def memo_body_html(text):
    """Any memo part: 'On the ...' subheadings, numbered paragraphs (4.1), lettered items (a.) and plain paragraphs."""
    out, items = [], []
    def flush():
        if items:
            out.append('<ol class="ac-ltr">' + "".join(items) + "</ol>")
            items.clear()
    for line in [x.strip() for x in str(text or "").split("\n") if x.strip()]:
        m_no = re.match(r"^(\d+\.\d+)\s+(.*)", line)
        m_lt = re.match(r"^([a-z])[.)]\s+(.*)", line)
        if m_lt:
            items.append(f'<li><span class="ltr">{m_lt.group(1)}.</span> {escape(m_lt.group(2))}</li>')
            continue
        flush()
        if m_no:
            out.append(f'<div class="np"><span class="no">{m_no.group(1)}</span><p>{escape(m_no.group(2))}</p></div>')
        elif re.match(r"^On (the )?\w", line) and len(line) < 110 and not line.endswith("."):
            out.append(f'<div class="oh">{escape(line)}</div>')
        else:
            out.append(f"<p>{escape(line)}</p>")
    flush()
    return "".join(out)


def _sentence(t):
    t = str(t or "").strip()
    return t[:1].upper() + t[1:]


def _clean_source(src):
    src = re.sub(r"\s*\((?:data/|[\w/]+\.csv)[^)]*\)", "", str(src or ""))
    src = src.replace("data/benchmarks/coa_comparators.csv", "COA annual audit reports")
    src = re.sub(r"data/benchmarks/[\w.]+", "", src).strip(" ;,")
    return _sentence(src)


def apprAIsal_fiscal(out, cost, req, peso):
    """Part V on screen: the estimate (PS, MOOE, CO), the fiscal table, and the cost references in a dropdown."""
    lo, hi = out["estimate"]["low"], out["estimate"]["high"]
    ui.html('<div class="ac-sec">Estimated budgetary requirements of the new entity</div>')
    if out["estimate"].get("applies") is False:
        ui.html('<div class="ac-out"><p>The bill does not create a new office, so the estimate of Personnel Services, MOOE and '
                'Capital Outlay for a new entity does not apply. Its requirements come from the program\'s benefits and implementation '
                'costs, which depend on its coverage; see the table below.</p></div>')
    else:
        _est_table(lo, hi, peso)
    ui.html('<div class="ac-sec">Fiscal and budgetary requirements</div>')
    _fis_table(out)
    _cost_refs(cost, req, peso, out["estimate"].get("applies") is not False)


def _est_table(lo, hi, peso):
    ui.table(["Requirement", f"Lower estimate ({lo['headcount']:,} positions)", f"Upper estimate ({hi['headcount']:,} positions)"],
             [["Personnel Services (PS)", peso(lo["ps"]), peso(hi["ps"])],
              ["Maintenance and Other Operating Expenses (MOOE)", peso(lo["mooe"]), peso(hi["mooe"])],
              ["Capital Outlay (CO), first year only", peso(lo["co"]), peso(hi["co"])],
              ["<b>Total, first year</b>", f"<b>{peso(lo['total'])}</b>", f"<b>{peso(hi['total'])}</b>"],
              ["Every year thereafter (PS and MOOE)", peso(lo["recurring"]), peso(hi["recurring"])]], cls="est")


def _fis_table(out):
    ui.html('<div class="ac-wide"><table class="ac-tbl cmp fis6"><thead><tr>' + "".join(f"<th>{h}</th>" for h in (
        "Fiscal requirement", "Provision", "What the bill provides", "Recommended budgetary consideration", "Recommendation", "Risks"))
        + "</tr></thead><tbody>" + "".join(
            f"<tr><td><b>{escape(r.get('item', ''))}</b></td><td>{escape(r.get('provision', ''))}</td><td>{escape(r.get('existing', ''))}</td>"
            f"<td>{escape(r.get('consideration', ''))}</td><td>{escape(r.get('recommendation', ''))}</td><td>{escape(r.get('risks', ''))}</td></tr>"
            for r in out.get("fiscal_rows") or []) + "</tbody></table></div>")


def _cost_refs(cost, req, peso, applies=True):
    if not applies:
        return
    with st.expander("Cost assumptions and similar agencies used for comparison (reference)"):
        st.caption(f"The estimate above uses the 2026 salary schedule for Personnel Services and DBM costing parameters for MOOE and "
                   f"Capital Outlay ({req['basis']}). Figures are an order of magnitude for a preliminary review, not a budget proposal.")
        ui.html("<p><b>Assumptions</b></p>")
        ui.table(["Assumption", "Source", "To verify"],
                 [[escape(_sentence(a["assumption"])), escape(_clean_source(a["source"])), "Yes" if a.get("to_verify") else "No"]
                  for a in cost["assumptions"]], cls="asm")
        ui.html("<p><b>Parameters for MOOE and Capital Outlay</b></p>")
        ui.table(["Item", "Parameter"], [[escape(k), escape(_sentence(v))] for k, v in list(req["mooe_notes"]) + list(req["co_notes"])], cls="asm")
        comps = cost["method_b_comparators"]["comparators"]
        if comps:
            ui.html("<p><b>Similar agencies, FY 2026 budget</b></p>")
            ui.table(["Agency", "Authorized positions", "Personnel Services", "Overhead MOOE", "Operating cost per position", "Source"],
                     [[escape(c["agency"]), f"{c['positions']:,}", peso(c["personnel_services"]), peso(c["mooe_overhead"]),
                       peso(c["per_position"]), escape(_clean_source(c["source"]))] for c in comps], cls="asm")
        if cost.get("coa_crosscheck"):
            ui.html("<p><b>Cross-check: COA audited spending per staff member (includes programs; not used in the estimate)</b></p>")
            ui.table(["Agency", "Year", "Spending per staff member", "Source"],
                     [[escape(c["agency"]), escape(str(c["year"])), peso(c["per_staff"]), escape(_clean_source(c["source"]))]
                      for c in cost["coa_crosscheck"]], cls="asm")


def apprAIsal_dup(out):
    dups = out.get("duplications") or []
    ui.html('<div class="ac-sec">Possible duplication of functions</div>')
    if not dups:
        ui.html('<div class="ac-out"><p>No duplication with existing offices was identified by TrAIce or CompAIre.</p></div>')
        return
    ui.table(["Provision of the bill", "Existing office or body", "Note", "Bill changes or abolishes the existing body?", "Assessment"],
             [[escape(d.get("function", "")), escape(d.get("existing", "")), escape(d.get("note", "")),
               "Yes" if d.get("intent_to_abolish") else "No", escape(d.get("assessment", ""))] for d in dups], cls="dup")


def referrals_table(out):
    refs = out.get("referrals") or []
    ui.html('<div class="ac-sec">DBM bureaus and offices to consult</div>')
    if not refs:
        ui.html('<div class="ac-out"><p>No referral identified.</p></div>')
        return
    ui.html('<div class="ac-note">Functions from the DBM Charter (CY 2026); the Budget and Management Bureau is matched from the agencies '
            'named in the bill and the coverage lists in the DBM Central Office Directory.</div>')
    ui.table(["Bureau or office", "Function", "Why consult", "Memo part"],
             [[f"<b>{escape(r.get('bureau', ''))}</b><div class='ttl'>{escape(r.get('name', ''))}</div>"
               + (f"<div class='ttl'>{escape(r['email'])}</div>" if r.get("email") else ""), escape(r.get("function", "")),
               escape(r.get("why", "")), escape(r.get("parts", ""))] for r in refs], cls="ref")


def _facts_cell(v, key):
    if not v:
        return "not stated"
    out = []
    for x in v if isinstance(v, list) else [v]:
        if isinstance(x, (list, tuple)) and len(x) == 2:
            val, sec = x
            if key == "head_salary_grades":
                val = f"SG {val}"
            elif key == "peso_amounts":
                val = f"₱{float(val):,.0f} million" if float(val) < 100000 else f"₱{float(val):,.0f}"
            elif key == "members":
                val = f"{val} members"
            out.append(f"{val} (Sec. {sec})")
        else:
            out.append(str(x))
    return "; ".join(out)


FACT_LABELS = {"head_salary_grades": "Salary grade of the head", "members": "Composition", "peso_amounts": "Amounts stated",
               "funding_source": "Source of funds", "abolishes_or_transfers_in_sections": "Abolishes or transfers offices",
               "n_sections": "Number of sections"}


def compare_plain(bid, ref, facts, aligned):
    """Step 2 without AI: key facts side by side, and how each section matches."""
    a, b = label(bid).split(" (")[0], label(ref).split(" (")[0]
    same = sum(1 for x in aligned if x["status"] == "same")
    changed = sum(1 for x in aligned if x["status"] == "changed")
    only_a = sum(1 for x in aligned if x["a_section"] and not x["b_section"])
    only_b = sum(1 for x in aligned if x["b_section"] and not x["a_section"])
    ui.notice(f"<b>Before any AI is used:</b> ActCheck matched the sections of {escape(a)} with those of {escape(b)}. "
              f"{same} are nearly the same, {changed} are changed, {only_a} appear only in {escape(a)} and {only_b} only in {escape(b)}.", "navy")
    rows = []
    for k, lab in FACT_LABELS.items():
        f = facts.get(k)
        if not f:
            continue
        ta, tb = f.get("target"), f.get("reference")
        cell_a = str(ta) if k == "n_sections" else escape(_facts_cell(ta, k))
        cell_b = str(tb) if k == "n_sections" else escape(_facts_cell(tb, k))
        rows.append([escape(lab), cell_a, cell_b, '<span class="ac-badge red">Different</span>' if f.get("differs") else "Same"])
    ui.html("<p><b>Key facts</b></p>")
    ui.table(["Item", a, b, ""], rows)
    def closeness(x):
        if not x["b_section"]:
            return f"Only in {a}"
        if not x["a_section"]:
            return f"Only in {b}"
        s = x.get("similarity") or 0
        return "Nearly the same" if s >= 0.85 else "Similar, with changes" if s >= 0.45 else "Mostly rewritten"
    ui.html("<p><b>Section by section</b></p>")
    ui.table([f"{a} section", f"Matching {b} section", "How close"],
             [[escape(f"Sec. {x['a_no']}. {x['a_heading']}") if x["a_section"] else "–",
               escape(f"Sec. {x['b_no']}. {x['b_heading']}") if x["b_section"] else "–",
               closeness(x)] for x in aligned])


def appraise(rev, cost, peso, checks=None, redteam=None):
    """Step 3: ApprAIsal."""
    c1, c2, c3 = st.columns(3)
    c1.metric("Entity type", cost["entity_type"])
    c2.metric("First-year cost range", f"{peso(cost['range']['low'])} – {peso(cost['range']['high'])}")
    c3.metric("Amount stated in the bill", ", ".join(peso(x["pesos"]) for x in cost["stated_in_bill"]) or "none")
    with st.expander("Cost assumptions and similar agencies used for comparison"):
        a = pd.DataFrame(cost["assumptions"])
        st.dataframe(a, use_container_width=True, hide_index=True)
        comp = pd.DataFrame([{"Agency": c["agency"], "Authorized positions": c["positions"], "Personnel Services": peso(c["personnel_services"]),
                              "Overhead MOOE": peso(c["mooe_overhead"]), "Overhead MOOE / PS": f"{c['overhead_mooe_share']:.0%}",
                              "Operating cost per position": peso(c["per_position"]), "Source": c["source"]}
                             for c in cost["method_b_comparators"]["comparators"]])
        st.markdown("**Similar agencies, FY 2026 budget (used in the range)**")
        st.dataframe(comp, use_container_width=True, hide_index=True)
        if cost.get("coa_crosscheck"):
            st.markdown("**Cross-check: COA audited spending per staff member (includes programs; not used in the range)**")
            st.dataframe(pd.DataFrame([{"Agency": c["agency"], "Year": c["year"], "Spending per staff member": peso(c["per_staff"]), "Source": c["source"]}
                                       for c in cost["coa_crosscheck"]]), use_container_width=True, hide_index=True)
    if not rev:
        return
    ui.html(f'<div class="ac-out"><p><b>Summary.</b> {escape(short(rev.get("summary"), 700))}</p>'
            f'<p><b>Fiscal.</b> {escape(short((rev.get("fiscal") or {}).get("narrative"), 600))}</p>'
            + (f'<p><b>Policy context.</b> {escape(short(rev.get("policy_context"), 400))}</p>' if rev.get("policy_context") else "")
            + '</div>')
    if checks:
        verification(checks.get("citations"))
        for x in checks.get("unsupported_numbers", []):
            ui.notice(f"<b>Amount not found in the cost estimate or the bill:</b> {escape(str(x))}", "red")
        for x in checks.get("governance_flags", []):
            ui.notice(f"<b>Governance rule:</b> {escape(str(x))}", "red")
    risks = rev.get("risks", [])
    if risks:
        ui.html("<p><b>Key risks</b></p>")
        ui.table(["#", "Risk"], [[str(i), escape(short(r, 260))] for i, r in enumerate(risks, 1)], mono_cols=(0,))
    with st.expander("History, differences and existing-law overlaps (full text)"):
        for k, t in (("history", "Legislative history"), ("differences", "Substantial differences"), ("existing_law", "Existing law")):
            if rev.get(k):
                st.markdown(f"**{t}.** {rev[k]}")
    if redteam:
        sev = redteam.get("issues", [])
        n_med = sum(1 for i in sev if i.get("severity") in ("high", "medium"))
        ui.notice(f"<b>Second reviewer:</b> {escape(redteam.get('release_recommendation', ''))} · {len(sev)} issues raised, {n_med} of high or medium importance.",
                  "red" if n_med else "")
        with st.expander("Issues raised by the second reviewer"):
            ui.table(["Severity", "Where", "Problem"], [[f'<span class="ac-badge {"red" if i.get("severity") in ("high", "medium") else ""}">'
                                                         f'{escape(i.get("severity", ""))}</span>', escape(short(i.get("where"), 60)),
                                                         escape(short(i.get("problem"), 240))] for i in sev])
