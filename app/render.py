"""Concise displays of each agent's output for the review workspace.

Lead with the finding, keep tables short (one line per row), and put the evidence quotes in an
expander so nothing is lost but the page stays readable.
"""
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


def trace(pack, out=None, checks=None):
    """Step 1: TrAIce."""
    p = pack["profile"]
    entity = (out or {}).get("entity_proposed") or p.get("entity") or "not detected"
    ui.html(f'<div class="ac-out"><p><b>Entity proposed:</b> {escape(entity)}. '
            + (f"<b>Substitutes:</b> {escape(', '.join(p['substitutes']))}. " if p.get("substitutes") else "")
            + f"<b>Text:</b> {'recognized from a scanned PDF' if p['text_source'] == 'ocr' else 'read from the PDF'}, {p['n_sections']} sections.</p></div>")
    if out:
        verification(checks)
        rel = out.get("related", [])
        ui.html("<p><b>Related measures</b></p>")
        ui.table(["Bill", "Relationship", "Why"], [[escape(label(r.get("id"))), f'<span class="ac-badge navy">{escape(r.get("relationship", ""))}</span>',
                                                   escape(short(r.get("basis"), 160))] for r in rel], mono_cols=(0,))
        ov = out.get("existing_law_overlaps", [])
        if ov:
            ui.html("<p><b>Existing laws it touches</b></p>")
            ui.table(["Law", "Overlap"], [[escape(label(o.get("law"))), escape(short(o.get("overlap"), 220))] for o in ov], mono_cols=(0,))
        quotes((checks or []) or [dict(section=r.get("section"), quote=r.get("quote")) for r in rel + ov], "q_trace")
        if out.get("gaps"):
            with st.expander(f"Gaps the agent could not close ({len(out['gaps'])})"):
                for g in out["gaps"]:
                    st.markdown(f"- {g}")
    else:
        ui.notice("<b>Before any AI is used:</b> the bills whose wording is most similar to this one, and the laws it cites or closely resembles.", "navy")
        ui.table(["Bill", "Wording in common", "Likely relationship", "Title"],
                 [[escape(label(r["id"])), f"{r['similarity']:.0%}" if r.get("similarity") is not None else "–",
                   escape(r.get("baseline_label", "")), escape(short(r.get("title"), 110))] for r in pack["related"][:10]], mono_cols=(0, 1))
        if pack.get("laws"):
            ui.table(["Law", "Why listed", "Title"], [[escape(label(l["law"])), escape(l.get("why", "")), escape(short(l.get("title"), 120))]
                                                     for l in pack["laws"][:8]], mono_cols=(0,))


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
    """Step 3: AppraisAI."""
    c1, c2, c3 = st.columns(3)
    c1.metric("Entity type", cost["entity_type"])
    c2.metric("First-year cost range", f"{peso(cost['range']['low'])} – {peso(cost['range']['high'])}")
    c3.metric("Amount stated in the bill", ", ".join(peso(x["pesos"]) for x in cost["stated_in_bill"]) or "none")
    with st.expander("Cost assumptions and similar agencies used for comparison"):
        a = pd.DataFrame(cost["assumptions"])
        st.dataframe(a, use_container_width=True, hide_index=True)
        st.dataframe(pd.DataFrame(cost["method_b_comparators"]["comparators"]), use_container_width=True, hide_index=True)
    if not rev:
        return
    ui.html(f'<div class="ac-out"><p><b>Summary.</b> {escape(short(rev.get("summary"), 700))}</p>'
            f'<p><b>Fiscal.</b> {escape(short((rev.get("fiscal") or {}).get("narrative"), 600))}</p></div>')
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
