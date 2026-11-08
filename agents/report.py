"""Preliminary report (Markdown and Word) assembled from a bill's saved review state."""
from agents.names import APP_NAME, AGENT1, AGENT2, AGENT3
import io
import json

from pipeline.compare import load
from agents import store
from agents.costing import cost_range, peso
from agents.appraisal import LABEL


def sections(bid):
    """Ordered (heading, list-of-paragraphs) for the report."""
    bills, _ = load()
    b = bills[bid]
    rec = store.load(bid)
    rev = (rec.get("review") or {}).get("output") or {}
    res = (rec.get("research") or {}).get("output") or {}
    dia = (rec.get("diagnosis") or {}).get("output") or {}
    rt = (rec.get("redteam") or {}).get("output") or {}
    cost = cost_range(bid)
    out = [("Bill", [f"{b['label']} ({b['congress']}th Congress): {b['title']}", f"Review status: {rec.get('status', 'new')}"])]
    out.append(("Summary", [rev.get("summary") or f"{AGENT3} review not yet run."]))
    hist = [rev.get("history", "")] if rev.get("history") else [f"{r.get('id')}: {r.get('relationship')}. {r.get('basis', '')}" for r in res.get("related", [])]
    out.append(("Legislative history and related measures", hist or [f"{AGENT1} not yet run."]))
    diffs = [rev.get("differences", "")] if rev.get("differences") else [f"{d.get('category')} ({d.get('fiscal_direction')}): {d.get('description')}" for d in dia.get("differences", [])]
    out.append(("Substantial differences", diffs or [f"{AGENT2} not yet run."]))
    laws = [rev.get("existing_law", "")] if rev.get("existing_law") else [f"{o.get('law')}: {o.get('overlap')}" for o in res.get("existing_law_overlaps", [])]
    out.append(("Overlap with existing law and agencies", laws or ["Not yet assessed."]))
    fis = [f"Costing engine, first full year: {peso(cost['range']['low'])} to {peso(cost['range']['high'])} ({cost['entity_type']}).",
           "Stated in the bill: " + (", ".join(f"{peso(x['pesos'])} [{x['section']}]" for x in cost["stated_in_bill"]) or "no amount stated."),
           (rev.get("fiscal") or {}).get("narrative", "")]
    fis += [f"Assumption: {a['assumption']} (source: {a['source']}){' - to verify' if a.get('to_verify') else ''}" for a in cost["assumptions"][:8]]
    out.append(("Fiscal implications", [x for x in fis if x]))
    out.append(("Implementation risks", rev.get("risks") or ["Not yet assessed."]))
    comments = rec.get("comments") or rev.get("preliminary_comments", [])
    comments = [c for c in comments if c.get("include", True)]
    out.append(("Preliminary comments (draft)", [f"{i}. {c.get('comment')} [{c.get('section', '')}]" for i, c in enumerate(comments, 1)] or [f"{AGENT3} review not yet run."]))
    out.append(("Points for the reviewer to verify", rev.get("checklist") or ["-"]))
    if rt:
        out.append(("Red-team findings", [f"Recommendation: {rt.get('release_recommendation')}"] +
                    [f"[{i.get('severity')}] {i.get('where')}: {i.get('problem')}" for i in rt.get("issues", [])]))
    return out


def markdown(bid):
    L = [f"# {APP_NAME} preliminary report: {load()[0][bid]['label']}", f"_{LABEL}_", ""]
    for h, paras in sections(bid):
        L += [f"## {h}"] + list(paras)
    return "\n\n".join(L)


def docx_bytes(bid):
    from docx import Document
    from docx.shared import Pt
    doc = Document()
    st = doc.styles["Normal"]
    st.font.name, st.font.size = "Arial", Pt(10.5)
    doc.add_heading(f"{APP_NAME} preliminary report: {load()[0][bid]['label']}", level=1)
    p = doc.add_paragraph(LABEL)
    p.runs[0].italic = True
    for h, paras in sections(bid):
        doc.add_heading(h, level=2)
        for x in paras:
            doc.add_paragraph(x)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()
