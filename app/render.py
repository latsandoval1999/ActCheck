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
            + f"<b>Text:</b> {escape(p['text_source'])}, {p['n_sections']} sections.</p></div>")
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
        ui.notice("Rules-only evidence (no AI yet): the closest bills by text similarity and the laws the bill cites or resembles.", "navy")
        ui.table(["Bill", "Similarity", "Likely relationship", "Title"],
                 [[escape(label(r["id"])), f"{r['similarity']:.2f}" if r.get("similarity") is not None else "–",
                   escape(r.get("baseline_label", "")), escape(short(r.get("title"), 110))] for r in pack["related"][:10]], mono_cols=(0, 1))
        if pack.get("laws"):
            ui.table(["Law", "Why listed", "Title"], [[escape(label(l["law"])), escape(l.get("why", "")), escape(short(l.get("title"), 120))]
                                                     for l in pack["laws"][:8]], mono_cols=(0,))


FISCAL = {"likely raises cost": "red", "likely lowers cost": "green", "no cost effect": "", "unclear": "gold"}


def compare(out, checks=None, baseline_md=None):
    """Step 2: CompAIre."""
    if not out:
        ui.notice("Rules-only comparison (no AI yet): section-by-section alignment and fact differences with the reference bill.", "navy")
        with st.expander("Show the rules-only comparison", expanded=True):
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
        with st.expander("Corrections to the rules-only alignment, and gaps"):
            for c in extra[0]:
                st.markdown(f"- **{c.get('target_section')} ↔ {c.get('reference_section')}**: {c.get('note')}")
            for g in extra[1]:
                st.markdown(f"- Gap: {g}")


def appraise(rev, cost, peso, checks=None, redteam=None):
    """Step 3: AppraisAI."""
    c1, c2, c3 = st.columns(3)
    c1.metric("Entity type", cost["entity_type"])
    c2.metric("First-year cost range", f"{peso(cost['range']['low'])} – {peso(cost['range']['high'])}")
    c3.metric("Amount stated in the bill", ", ".join(peso(x["pesos"]) for x in cost["stated_in_bill"]) or "none")
    with st.expander("Costing assumptions and comparator agencies"):
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
            ui.notice(f"<b>Figure not from the costing engine or the bill:</b> {escape(str(x))}", "red")
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
        ui.notice(f"<b>Red-teamer:</b> {escape(redteam.get('release_recommendation', ''))} · {len(sev)} issues, {n_med} high or medium.",
                  "red" if n_med else "")
        with st.expander("Red-team issues"):
            ui.table(["Severity", "Where", "Problem"], [[f'<span class="ac-badge {"red" if i.get("severity") in ("high", "medium") else ""}">'
                                                         f'{escape(i.get("severity", ""))}</span>', escape(short(i.get("where"), 60)),
                                                         escape(short(i.get("problem"), 240))] for i in sev])
