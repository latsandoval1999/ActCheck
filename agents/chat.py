"""'Ask about this bill': grounded chat over one bill's workspace, with citation checks."""
import json
import re

from pipeline.compare import load, related_bills
from agents import store
from agents.costing import cost_range

CITE = re.compile(r"\[((?:law|meta):[A-Za-z0-9\-]+|[A-Za-z]+-[A-Za-z0-9\-]+:(?:s\d+|note))\]")


def workspace(bid, max_sections=40):
    from agents.pipeline_agents import _sections_block
    bills, _ = load()
    b = bills[bid]
    rec = store.load(bid)
    parts = [f"BILL: {bid} ({b['label']}, {b['congress']}th Congress, text: {b['text_source']})\nTITLE: {b['title']}",
             f"RULE-BASED FACTS: {json.dumps(b['facts'], ensure_ascii=False)}",
             f"LAWS CITED: {json.dumps(b.get('laws_cited', {}))}",
             f"COSTING ENGINE (summary): {json.dumps({k: v for k, v in cost_range(bid).items() if k in ('entity_type', 'range', 'stated_in_bill', 'assumptions')}, ensure_ascii=False)}",
             "RELATED (baseline): " + json.dumps([{k: r[k] for k in ('id', 'similarity', 'title')} for r in related_bills(bid, top=8)], ensure_ascii=False),
             _sections_block(bid, limit=max_sections)]
    for key, label in (("research", "TrAIce output"), ("diagnosis", "CompAIre output"), ("review", "AppraisAI review"), ("redteam", "Red-team findings")):
        if rec.get(key):
            parts.append(f"{label.upper()}: {json.dumps(rec[key].get('output', rec[key]), ensure_ascii=False)[:12000]}")
    return "\n\n".join(parts)


def check_citations_in(text):
    from agents.verify import section_text
    found = CITE.findall(text)
    return [{"citation": c, "exists": section_text(c) is not None} for c in dict.fromkeys(found)]


def ask(bid, history, question):
    from agents import llm
    system = llm.prompt("chat") + "\n\nBILL WORKSPACE:\n" + workspace(bid)
    msgs = [m for m in history if m["role"] in ("user", "assistant")] + [{"role": "user", "content": question}]
    text, meta = llm.chat("chat", system, msgs[-12:])
    return text, check_citations_in(text), meta
