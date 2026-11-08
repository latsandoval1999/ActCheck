"""The three agents. Each one: build context from the corpus -> call the model ->
check the output deterministically -> return result plus checks.

Context is kept small on purpose: only the sections an agent needs, each tagged
with its section ID, so citations can be verified.
"""
import json

from agents import llm
from agents.verify import check_citations, numbers_supported, governance_flags
from pipeline.compare import load, related_bills, align, summary

MAX_SECTION_CHARS = 1500


def _sections_block(bid, only=None, limit=60):
    bills, secs = load()
    rows = []
    for s in secs.get(bid, [])[:limit]:
        if only and s["no"] not in only:
            continue
        rows.append(f"[{s['id']}] {s['heading']}: {s['text'][:MAX_SECTION_CHARS]}")
    b = bills[bid]
    head = f"=== {bid} | {b['label']} | Congress: {b['congress'] or 'n/a'} | text: {b['text_source']}\nTITLE: {b['title']}"
    return head + "\n" + "\n".join(rows)


def _key_sections(bid):
    """Short-title, creation, composition, powers, appropriations and abolition sections."""
    _, secs = load()
    keys = ("short title", "creat", "establish", "composition", "powers", "appropriat", "abolish", "transfer", "attached", "executive director", "secretary")
    return [s["no"] for s in secs.get(bid, []) if any(k in s["heading"].lower() for k in keys)]


# Agent 1 lives in agents/research.py


# ---------- Agent 2: Diagnosis and design ----------
def run_diagnosis(target, reference):
    rows = align(target, reference)
    user = (f"Target: {target}\nReference: {reference}\nBaseline alignment summary: {json.dumps(summary(rows))}\n"
            f"Baseline alignment rows: {json.dumps(rows)}\n\nTARGET SECTIONS:\n{_sections_block(target)}\n\n"
            f"REFERENCE SECTIONS:\n{_sections_block(reference)}")
    text, meta = llm.call("diagnosis", llm.prompt("p2_diagnosis"), user, max_tokens=6000)
    out = llm.parse_json(text)
    claims = []
    for d in out.get("differences", []):
        if d.get("target_section"):
            claims.append({"claim": d.get("description", ""), "section": d["target_section"], "quote": d.get("target_quote", "")})
        if d.get("reference_section"):
            claims.append({"claim": d.get("description", ""), "section": d["reference_section"], "quote": d.get("reference_quote", "")})
    return {"output": out, "checks": check_citations(claims), "baseline": {"summary": summary(rows), "rows": rows}, "meta": meta}


# ---------- Agent 3: Appraisal and governance (with red-teamer) ----------
def run_appraisal(bid, research=None, diagnosis=None, benchmarks=""):
    bills, secs = load()
    b = bills[bid]
    user = (f"Target bill: {bid} ({b['label']})\nExtracted facts (rule-based): {json.dumps(b['facts'])}\n"
            f"Research agent output: {json.dumps(research or {})}\nDiagnosis agent output: {json.dumps(diagnosis or {})}\n"
            f"Costing benchmarks supplied by reviewer (may be empty): {benchmarks or 'none'}\n\n"
            f"TARGET SECTIONS:\n{_sections_block(bid)}")
    text, meta = llm.call("appraisal", llm.prompt("p3_appraisal"), user, max_tokens=6000)
    draft = llm.parse_json(text)
    sources = [s["text"] for s in secs.get(bid, [])] + [benchmarks or ""]
    checks = {
        "citations": check_citations(draft.get("claims", [])),
        "unsupported_numbers": numbers_supported(json.dumps(draft.get("fiscal", {})), sources),
        "governance_flags": governance_flags(json.dumps(draft)),
    }
    rt_user = (f"DRAFT:\n{json.dumps(draft, ensure_ascii=False)}\n\nAUTOMATED CHECKS:\n{json.dumps(checks)}\n\n"
               f"SOURCE SECTIONS:\n{_sections_block(bid)}\n\nBENCHMARKS: {benchmarks or 'none'}")
    rt_text, rt_meta = llm.call("redteam", llm.prompt("p3_redteam"), rt_user)
    return {"draft": draft, "checks": checks, "redteam": llm.parse_json(rt_text), "meta": [meta, rt_meta]}
