"""CompAIre (Agent 2): Policy Diagnosis and Design.

For a TARGET bill and a REFERENCE bill (earlier version, refiled copy, counterpart or
substitute), the agent:
  1. diagnoses the policy problem each bill says it addresses (explanatory notes),
  2. lists SUBSTANTIAL differences (mandate, structure, powers, staffing, funding,
     abolition/transfer, oversight) with the fiscal direction of each,
  3. sets out the design options found across the bill family (e.g. department vs
     authority vs office in an existing department), and
  4. corrects the non-AI section alignment where it is wrong.

Rules-only parts (no AI): fact diff, section alignment, family design variants.
Checks after the model: every quote verified; differences claimed in sections the
baseline found identical are flagged; labels must come from the allowed lists.

    python -m agents.diagnosis SB-20-1624 SB-20-1199                 # baseline report
    python -m agents.diagnosis SB-20-1624 SB-20-1199 --prompt > p.txt # prompt for a chat
    python -m agents.diagnosis SB-20-1624 SB-20-1199 --check reply.json
"""
import json
import re
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

from pipeline.compare import load, align, summary
from agents.research import entity_name

ROOT = Path(__file__).resolve().parents[1]
CATEGORIES = {"mandate", "structure", "powers", "staffing and compensation", "funding",
              "abolition or transfer of existing offices", "oversight and reporting", "other"}
DIRECTIONS = {"likely raises cost", "likely lowers cost", "no cost effect", "unclear"}
MAX_CHARS = 1400


# ---------------- rules only ----------------
def _fact_summary(bid):
    bills, _ = load()
    f = bills[bid]["facts"]
    return {
        "head_salary_grades": sorted({(x["sg"], x["section"]) for x in f["salary_grades"]}),
        "members": [(x["value"], x["section"]) for x in f["members"]],
        "peso_amounts": [(round(x["pesos"] / 1e6, 2), x["section"]) for x in f["amounts"]],
        "abolishes_or_transfers_in_sections": [x["section"] for x in f["abolishes_or_transfers"]],
        "funding_source": sorted({(x["source"], x["section"]) for x in f["funding_source"]}),
        "n_sections": bills[bid]["n_sections"],
    }


def fact_diff(target, reference):
    """Side-by-side rule-based facts; 'differs' marks fields whose values differ."""
    a, b = _fact_summary(target), _fact_summary(reference)
    out = {}
    for k in a:
        va = [x[0] if isinstance(x, tuple) else x for x in (a[k] if isinstance(a[k], list) else [a[k]])]
        vb = [x[0] if isinstance(x, tuple) else x for x in (b[k] if isinstance(b[k], list) else [b[k]])]
        out[k] = {"target": a[k], "reference": b[k], "differs": sorted(map(str, va)) != sorted(map(str, vb))}
    return out


def family_designs(bid):
    """How bills in the same family name the body they create (design variants)."""
    bills, _ = load()
    fam = bills[bid]["family"]
    names = Counter()
    examples = {}
    for b in bills.values():
        if b["family"] != fam or b["is_law"]:
            continue
        e = entity_name(b["title"]).upper()
        e = re.sub(r"\s+", " ", e)[:90]
        if e:
            names[e] += 1
            examples.setdefault(e, b["id"])
    return [{"design": n, "bills": c, "example": examples[n]} for n, c in names.most_common(8)]


def _note(bid, n=2500):
    bills, _ = load()
    return bills[bid]["explanatory_note"][:n]


def build_messages(target, reference):
    from agents import llm
    bills, secs = load()
    rows = align(target, reference)
    sec_t = {s["id"]: s for s in secs.get(target, [])}
    sec_r = {s["id"]: s for s in secs.get(reference, [])}

    def block(sid, pool):
        s = pool[sid]
        return f"[{sid}] {s['heading']}: {s['text'][:MAX_CHARS]}"

    same, diff_blocks = [], []
    for r in rows:
        if r["status"] == "same":
            same.append(f"{r['a_section']} = {r['b_section']} ({r['a_heading'][:50]}; similarity {r['similarity']})")
        else:
            pair = []
            if r["a_section"]:
                pair.append("TARGET " + block(r["a_section"], sec_t))
            if r["b_section"]:
                pair.append("REFERENCE " + block(r["b_section"], sec_r))
            diff_blocks.append(f"-- alignment: {r['status']} (similarity {r['similarity']})\n" + "\n".join(pair))
    user = (
        f"TARGET: {target} ({bills[target]['label']}, {bills[target]['congress']}th Congress, text: {bills[target]['text_source']})\n"
        f"TITLE: {bills[target]['title']}\n"
        f"REFERENCE: {reference} ({bills[reference]['label']}, {bills[reference]['congress']}th Congress, text: {bills[reference]['text_source']})\n"
        f"TITLE: {bills[reference]['title']}\n\n"
        f"RULE-BASED FACT DIFF (no AI; may miss things): {json.dumps(fact_diff(target, reference))}\n\n"
        f"DESIGN VARIANTS IN THIS BILL FAMILY (from titles, no AI): {json.dumps(family_designs(target))}\n\n"
        f"BASELINE ALIGNMENT SUMMARY: {json.dumps(summary(rows))}\n"
        f"SECTIONS THE BASELINE FOUND IDENTICAL (text omitted):\n" + "\n".join(same) + "\n\n"
        f"SECTIONS THAT DIFFER OR HAVE NO MATCH (full text):\n" + "\n\n".join(diff_blocks) + "\n\n"
        f"EXPLANATORY NOTE, TARGET (cite as {target}:note):\n{_note(target)}\n\n"
        f"EXPLANATORY NOTE, REFERENCE (cite as {reference}:note):\n{_note(reference)}")
    return llm.prompt("p2_diagnosis"), user, rows


# ---------------- checks ----------------
def check_output(out, target, reference):
    from agents.verify import check_citations, quote_found
    bills, _ = load()
    claims = []
    for d in out.get("differences", []):
        for side in ("target", "reference"):
            sid = d.get(f"{side}_section", "")
            if sid:
                claims.append({"claim": d.get("description", ""), "section": sid, "quote": d.get(f"{side}_quote", "")})
    for p in out.get("problem_diagnosis", {}).get("evidence", []):
        claims.append({"claim": p.get("point", ""), "section": p.get("section", ""), "quote": p.get("quote", "")})
    for o in out.get("design_options", []):
        if o.get("section"):
            claims.append({"claim": o.get("option", ""), "section": o["section"], "quote": o.get("quote", "")})
    checks = []
    for c in claims:
        if c["section"].endswith(":note"):  # explanatory-note citations
            bid = c["section"].rsplit(":", 1)[0]
            ok = bid in bills and quote_found(c["quote"], bills[bid]["explanatory_note"])
            checks.append({**c, "check": "verified" if ok else ("quote not found in section" if bid in bills else "section does not exist")})
        else:
            checks += check_citations([c])
    rows = align(target, reference)
    identical = {(r["a_section"], r["b_section"]) for r in rows if r["status"] == "same" and (r["similarity"] or 0) >= 0.97}
    flags = []
    for d in out.get("differences", []):
        if (d.get("target_section"), d.get("reference_section")) in identical:
            flags.append(f"Difference claimed in sections the baseline found near-identical: {d.get('target_section')} / {d.get('reference_section')}")
        if d.get("category") not in CATEGORIES:
            flags.append(f"Unknown category: {d.get('category')}")
        if d.get("fiscal_direction") not in DIRECTIONS:
            flags.append(f"Unknown fiscal direction: {d.get('fiscal_direction')}")
    return {"citations": checks, "flags": flags}


def run_agent(target, reference):
    from agents import llm
    system, user, rows = build_messages(target, reference)
    text, meta = llm.call("diagnosis", system, user, max_tokens=7000)
    out = llm.parse_json(text)
    return {"output": out, "checks": check_output(out, target, reference), "baseline": {"summary": summary(rows), "rows": rows},
            "facts": fact_diff(target, reference), "meta": meta}


# ---------------- output ----------------
def report_markdown(target, reference, out=None, checks=None):
    bills, _ = load()
    rows = align(target, reference)
    s = summary(rows)
    L = [f"# Diagnosis: {bills[target]['label']} compared with {bills[reference]['label']}",
         "_AI-assisted preliminary analysis for DBM reviewer validation._" if out else "_Baseline comparison (rules only, no AI)._", ""]
    L.append(f"**Section alignment (no AI):** {s['same']} same, {s['changed']} changed, {s['new in A']} only in {bills[target]['label']}, "
             f"{s['only in B']} only in {bills[reference]['label']}.")
    L += ["", "## Rule-based fact differences"]
    for k, v in fact_diff(target, reference).items():
        if v["differs"]:
            L.append(f"- **{k.replace('_', ' ')}**: {v['target']} vs {v['reference']}")
    if out:
        L += ["", f"## Verdict: {out.get('verdict', '')}", "", "## Policy problem"]
        pd_ = out.get("problem_diagnosis", {})
        L.append(pd_.get("problem", ""))
        for e in pd_.get("evidence", []):
            L.append(f"- {e.get('point', '')} [{e.get('section', '')}: \"{e.get('quote', '')}\"]")
        L += ["", "## Substantial differences"]
        for d in out.get("differences", []):
            L.append(f"- **{d.get('category')}** ({d.get('fiscal_direction')}): {d.get('description')} "
                     f"[{d.get('target_section') or '-'} / {d.get('reference_section') or '-'}]")
        if out.get("design_options"):
            L += ["", "## Design options in the bill family"]
            for o in out["design_options"]:
                L.append(f"- **{o.get('option')}** ({o.get('found_in', '')}): {o.get('trade_off', '')}")
        if out.get("baseline_corrections"):
            L += ["", "## Corrections to the baseline alignment"]
            for c in out["baseline_corrections"]:
                L.append(f"- {c.get('target_section')} / {c.get('reference_section')}: {c.get('note')}")
        if checks:
            ok = sum(c["check"] == "verified" for c in checks["citations"])
            L += ["", f"**Citation check:** {ok} of {len(checks['citations'])} verified."] + [f"- Flag: {f}" for f in checks["flags"]]
    else:
        L += ["", "## Sections that differ (baseline)"]
        for r in rows:
            if r["status"] != "same":
                L.append(f"- {r['status']}: {r['a_section'] or '-'} {r['a_heading'][:50]} | {r['b_section'] or '-'} {r['b_heading'][:50]} "
                         f"(similarity {r['similarity']})")
        L += ["", "## Design variants in the family (from titles)"] + [f"- {d['design']} ({d['bills']} bills, e.g. {d['example']})" for d in family_designs(target)]
    return "\n".join(L)


if __name__ == "__main__":
    a = sys.argv[1:]
    if len(a) < 2:
        sys.exit("usage: python -m agents.diagnosis TARGET REFERENCE [--prompt | --check reply.json]")
    t, r = a[0], a[1]
    if "--prompt" in a:
        system, user, _ = build_messages(t, r)
        print("=== SYSTEM PROMPT ===\n" + system + "\n=== USER MESSAGE ===\n" + user)
    elif "--check" in a:
        from agents.llm import parse_json
        out = parse_json(open(a[a.index("--check") + 1]).read())
        ch = check_output(out, t, r)
        for c in ch["citations"]:
            print(f"{c['check']:<28} {c['section']:<24} {c['quote'][:60]}")
        for f in ch["flags"]:
            print("FLAG:", f)
        ok = sum(c["check"] == "verified" for c in ch["citations"])
        print(f"\n{ok} of {len(ch['citations'])} citations verified; {len(ch['flags'])} flags.")
        log = ROOT / "logs" / "p2_runs.jsonl"
        log.parent.mkdir(exist_ok=True)
        with open(log, "a") as f:
            f.write(json.dumps({"target": t, "reference": r, "output": out, "checks": ch,
                                "meta": {"mode": "manual chat", "time": datetime.now(timezone.utc).isoformat(timespec="seconds")}},
                               ensure_ascii=False) + "\n")
        print(f"Saved to {log.relative_to(ROOT)}")
    else:
        print(report_markdown(t, r))
