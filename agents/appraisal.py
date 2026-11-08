"""AppraisAI (Agent 3): Policy Appraisal and Governance.

Four steps, each a separate model call with a human gate between them:

  review   -> preliminary review + verification checklist        (p3_appraisal.md)
  redteam  -> independent critique of the review                  (p3_redteam.md)
  memo     -> memorandum to the Secretary proposing comments      (p3_memo.md)
              (only from a review the reviewer has approved; position left as a placeholder)
  letter   -> letter to the committee chair / principal author    (p3_letter.md)
              (only after the reviewer has filled in the position in the memo)

Numbers come only from the costing engine (agents/costing.py) and the bill text.
Checks after every step: citations, unsupported peso figures, governance rules.

Command line (free route: paste the prompt into a chat, save the reply, check it):
    python -m agents.appraisal SB-20-1624 --step review --prompt > p.txt
    python -m agents.appraisal SB-20-1624 --step review --check reply.json
    python -m agents.appraisal SB-20-1624 --step redteam --draft review.json --prompt > p.txt
    python -m agents.appraisal SB-20-1624 --step memo --draft review_approved.json --prompt > p.txt
    python -m agents.appraisal SB-20-1624 --step letter --memo memo_with_position.txt --prompt > p.txt
"""
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

from pipeline.compare import load
from agents.costing import cost_range, peso, comparators

ROOT = Path(__file__).resolve().parents[1]
LABEL = "AI-assisted preliminary draft for DBM reviewer validation. Not an official position."
POSITION_PLACEHOLDER = "[POSITION TO BE DETERMINED BY THE REVIEWER"
MAX_CHARS = 1500


# ---------------- inputs ----------------
def _sections(bid, limit=60):
    from agents.pipeline_agents import _sections_block
    return _sections_block(bid, limit=limit)


def _latest(log_name, key, value):
    p = ROOT / "logs" / log_name
    if not p.exists():
        return None
    hit = None
    for line in open(p):
        r = json.loads(line)
        if r.get(key) == value:
            hit = r.get("output")
    return hit


def build_review_messages(bid, research=None, diagnosis=None, cost_overrides=None):
    from agents import llm
    bills, _ = load()
    b = bills[bid]
    research = research or _latest("p1_runs.jsonl", "target", bid)
    diagnosis = diagnosis or _latest("p2_runs.jsonl", "target", bid)
    cost = cost_range(bid, **(cost_overrides or {}))
    comps = [c for c in comparators() if c["agency"] in {x["agency"] for x in cost["method_b_comparators"]["comparators"]}]
    user = (f"TARGET BILL: {bid} ({b['label']}, {b['congress']}th Congress; text source: {b['text_source']})\nTITLE: {b['title']}\n\n"
            f"RULE-BASED FACTS (no AI): {json.dumps(b['facts'], ensure_ascii=False)}\n"
            f"LAWS CITED IN THE BILL: {json.dumps(b.get('laws_cited', {}))}\n\n"
            f"COSTING ENGINE OUTPUT (the ONLY permitted source of cost figures): {json.dumps(cost, ensure_ascii=False)}\n\n"
            f"COMPARATOR AGENCIES (COA audit reports): {json.dumps(comps, ensure_ascii=False)}\n\n"
            f"TRAICE (AGENT 1, EVIDENCE AND RESEARCH) OUTPUT: {json.dumps(research, ensure_ascii=False) if research else 'not run'}\n\n"
            f"COMPAIRE (AGENT 2, DIAGNOSIS AND DESIGN) OUTPUT: {json.dumps(diagnosis, ensure_ascii=False) if diagnosis else 'not run'}\n\n"
            f"TARGET SECTIONS:\n{_sections(bid)}")
    return llm.prompt("p3_appraisal"), user, cost


def build_redteam_messages(bid, draft):
    from agents import llm
    cost = cost_range(bid)
    checks = check_review(bid, draft)
    user = (f"DRAFT REVIEW:\n{json.dumps(draft, ensure_ascii=False)}\n\nAUTOMATED CHECKS (no AI):\n{json.dumps(checks, ensure_ascii=False)}\n\n"
            f"COSTING ENGINE OUTPUT:\n{json.dumps(cost, ensure_ascii=False)}\n\n"
            f"COMPARATOR TABLE (COA audit reports):\n{json.dumps(comparators(), ensure_ascii=False)}\n\nSOURCE SECTIONS:\n{_sections(bid)}")
    return llm.prompt("p3_redteam"), user


def build_memo_messages(bid, approved_review, bureau_inputs=""):
    from agents import llm
    bills, _ = load()
    user = (f"BILL: {bid} ({bills[bid]['label']}): {bills[bid]['title']}\n\n"
            f"APPROVED PRELIMINARY REVIEW (edited and approved by the reviewer):\n{json.dumps(approved_review, ensure_ascii=False)}\n\n"
            f"BUREAU INPUTS PASTED BY THE REVIEWER (may be empty): {bureau_inputs or 'none'}\n\n"
            f"CITED SECTIONS:\n{_sections(bid)}")
    return llm.prompt("p3_memo"), user


def build_letter_messages(bid, memo_text):
    from agents import llm
    if POSITION_PLACEHOLDER in memo_text:
        raise ValueError("The memo's position is still a placeholder. The reviewer must decide the position before a letter is drafted.")
    bills, _ = load()
    user = (f"BILL: {bid} ({bills[bid]['label']}): {bills[bid]['title']}\n\nAPPROVED MEMORANDUM (position decided by the reviewer):\n{memo_text}\n\n"
            f"CITED SECTIONS:\n{_sections(bid)}")
    return llm.prompt("p3_letter"), user


# ---------------- checks ----------------
PESO = re.compile(r"(?:₱|PHP|Php|P)\s?([\d,]+(?:\.\d+)?)\s*(billion|million|thousand)?", re.I)
MULT = {"billion": 1e9, "million": 1e6, "thousand": 1e3}


def _pesos_in(text):
    out = []
    for m in PESO.finditer(text):
        try:
            v = float(m.group(1).replace(",", ""))
        except ValueError:
            continue
        v *= MULT.get((m.group(2) or "").lower(), 1)
        if v >= 1000:
            out.append((m.group(0), v))
    return out


def allowed_numbers(bid):
    """Every peso figure the draft may use: costing engine output and amounts in the bill."""
    cost = cost_range(bid)
    vals = []

    def walk(x):
        if isinstance(x, dict):
            for v in x.values():
                walk(v)
        elif isinstance(x, list):
            for v in x:
                walk(v)
        elif isinstance(x, (int, float)) and x >= 1000:
            vals.append(float(x))
        elif isinstance(x, str):
            vals.extend(v for _, v in _pesos_in(x))
    walk(cost)
    for c in comparators():
        for k in ("appropriations_current", "allotments", "obligations"):
            if c[k]:
                vals.append(float(c[k]))
    _, secs = load()
    for s in secs.get(bid, []):
        vals.extend(v for _, v in _pesos_in(s["text"]))
    from agents.costing import salary_schedule
    vals.extend(float(v) for v in salary_schedule().values())
    return vals


def unsupported_numbers(bid, text):
    allowed = allowed_numbers(bid)
    bad = []
    for raw, v in _pesos_in(text):
        if not any(abs(v - a) <= max(0.01 * a, 1e5 if v >= 1e7 else 1) for a in allowed):
            bad.append(raw)
    return bad


OFFICIAL_NAME = re.compile(r"\b(?:Secretary|Undersecretary|Usec\.|Asec\.|Director)\s+[A-Z][a-z]+\s+[A-Z]", re.M)
FORBIDDEN = [r"\bapproved\s+by\b", r"\bsigned\b(?!\s*\])", r"\bwe\s+recommend\s+(?:the\s+)?(?:approval|disapproval|passage)\b",
             r"\bDBM\s+(?:supports|opposes|interposes no objection)\b"]


def governance_flags(text, kind):
    flags = [f"forbidden phrase: {p}" for p in FORBIDDEN if re.search(p, text, re.I)]
    if OFFICIAL_NAME.search(text):
        flags.append("possible name of an official: " + OFFICIAL_NAME.search(text).group(0))
    if LABEL.split(".")[0] not in text:
        flags.append("missing the AI-assisted preliminary draft label")
    if kind == "memo" and POSITION_PLACEHOLDER not in text:
        flags.append("memo must leave the position as the reviewer placeholder")
    if kind in ("memo", "letter") and "[SIGNATURE BLOCK" not in text:
        flags.append("missing the signature-block placeholder")
    return flags


def check_review(bid, draft):
    from agents.verify import check_citations
    text = json.dumps(draft, ensure_ascii=False)
    claims = list(draft.get("claims", [])) + [{"claim": c.get("comment", ""), "section": c.get("section", ""), "quote": c.get("quote", "")}
                                              for c in draft.get("preliminary_comments", []) if c.get("quote")]
    return {"citations": check_citations(claims),
            "unsupported_numbers": unsupported_numbers(bid, text),
            "governance_flags": governance_flags(text, "review")}


def check_document(bid, text, kind):
    return {"unsupported_numbers": unsupported_numbers(bid, text), "governance_flags": governance_flags(text, kind)}


# ---------------- live runs ----------------
def run_review(bid, research=None, diagnosis=None, cost_overrides=None):
    from agents import llm
    system, user, cost = build_review_messages(bid, research, diagnosis, cost_overrides)
    text, meta = llm.call("appraisal", system, user, max_tokens=7000)
    draft = llm.parse_json(text)
    return {"draft": draft, "cost": cost, "checks": check_review(bid, draft), "meta": meta}


def run_redteam(bid, draft):
    from agents import llm
    system, user = build_redteam_messages(bid, draft)
    text, meta = llm.call("redteam", system, user, max_tokens=4000)
    return {"redteam": llm.parse_json(text), "meta": meta}


def run_memo(bid, approved_review, bureau_inputs=""):
    """AppraisAI's memo draft as template fields (s1, s1_1, s2, s3_2, s3_3, s4, s5)."""
    from agents import llm
    system, user = build_memo_messages(bid, approved_review, bureau_inputs)
    text, meta = llm.call("memo", system, user, max_tokens=5000)
    out = llm.parse_json(text)
    return {"memo": out, "meta": meta}


def run_letter(bid, memo_text):
    """AppraisAI's letter draft as template fields (p1 to p4)."""
    from agents import llm
    system, user = build_letter_messages(bid, memo_text)
    text, meta = llm.call("letter", system, user, max_tokens=3000)
    return {"letter": llm.parse_json(text), "meta": meta}


def review_markdown(bid, draft, cost=None):
    bills, _ = load()
    cost = cost or cost_range(bid)
    f = draft.get("fiscal", {})
    L = [f"# Preliminary review: {bills[bid]['label']}", f"_{LABEL}_", "",
         "## 1. Summary of the bill", draft.get("summary", ""), "", "## 2. Legislative history and related measures", draft.get("history", ""),
         "", "## 3. Substantial differences from related measures", draft.get("differences", ""), "",
         "## 4. Overlap with existing law and agencies", draft.get("existing_law", ""), "", "## 5. Fiscal implications"]
    if f.get("can_estimate"):
        L.append(f"Estimated first-year cost: **{peso(cost['range']['low'])} to {peso(cost['range']['high'])}** (costing engine; see assumptions).")
    L.append(f.get("narrative", ""))
    for a in f.get("assumptions", []):
        L.append(f"- {a.get('assumption')} (source: {a.get('source')})")
    if f.get("missing_data"):
        L += ["", "Missing data:"] + [f"- {m}" for m in f["missing_data"]]
    L += ["", "## 6. Implementation risks"] + [f"- {r}" for r in draft.get("risks", [])]
    L += ["", "## 7. Points for the reviewer to verify"] + [f"- [ ] {c}" for c in draft.get("checklist", [])]
    if draft.get("preliminary_comments"):
        L += ["", "## 8. Preliminary comments (draft, for the reviewer to adopt, edit or drop)"]
        for i, c in enumerate(draft["preliminary_comments"], 1):
            L.append(f"{i}. {c.get('comment')} [{c.get('section', '')}]")
    return "\n".join(L)


# ---------------- command line ----------------
def _arg(a, flag):
    return a[a.index(flag) + 1] if flag in a else None


if __name__ == "__main__":
    from agents.llm import parse_json
    a = sys.argv[1:]
    bid = a[0]
    step = _arg(a, "--step") or "review"
    if "--prompt" in a:
        if step == "review":
            system, user, _ = build_review_messages(bid)
        elif step == "redteam":
            system, user = build_redteam_messages(bid, parse_json(open(_arg(a, "--draft")).read()))
        elif step == "memo":
            system, user = build_memo_messages(bid, parse_json(open(_arg(a, "--draft")).read()))
        else:
            system, user = build_letter_messages(bid, open(_arg(a, "--memo")).read())
        print("=== SYSTEM PROMPT ===\n" + system + "\n=== USER MESSAGE ===\n" + user)
    elif "--check" in a:
        raw = open(_arg(a, "--check")).read()
        if step == "review":
            out = parse_json(raw)
            ch = check_review(bid, out)
            for c in ch["citations"]:
                print(f"{c['check']:<28} {c['section']:<22} {c['quote'][:60]}")
        elif step == "redteam":
            out = parse_json(raw)
            ch = {"issues": len(out.get("issues", [])), "release_recommendation": out.get("release_recommendation")}
        else:
            out = raw
            ch = check_document(bid, raw, step)
        print(json.dumps({k: v for k, v in ch.items() if k != "citations"}, indent=1, ensure_ascii=False))
        log = ROOT / "logs" / "p3_runs.jsonl"
        log.parent.mkdir(exist_ok=True)
        with open(log, "a") as f:
            f.write(json.dumps({"target": bid, "step": step, "output": out, "checks": ch,
                                "meta": {"mode": "manual chat", "time": datetime.now(timezone.utc).isoformat(timespec="seconds")}},
                               ensure_ascii=False) + "\n")
        print(f"Saved to {log.relative_to(ROOT)}")
    else:
        c = cost_range(bid)
        print(f"Costing engine for {bid}: {peso(c['range']['low'])} to {peso(c['range']['high'])} ({c['entity_type']})")
        for x in c["assumptions"][:6]:
            print(" -", x["assumption"], "|", x["source"])
