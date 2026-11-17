"""Scheduled TrAIce runs by Claude, without an API key.

A scheduled Claude session (under the owner's Claude subscription) works through a queue of bills:
  1. bills a reviewer added to the Review workspace (listed in data/agent_runs/queue.txt), then
  2. the pilot: every Government organization and mandates bill with a full text (20th Congress first).
For each bill the session reads the exact TrAIce prompt (agents/prompts/p1_research.md plus the bill's evidence),
writes the JSON answer, and saves it here. ActCheck checks every citation before saving; nothing is saved
until every cited passage is found in the cited section. The site then shows the output as "Prepared by TrAIce (Claude)".

Commands
  python scripts/traice_batch.py status              counts done and pending
  python scripts/traice_batch.py next [N]            the next N bills to run (default 12)
  python scripts/traice_batch.py prompt BILL         writes the prompt to runs_tmp/BILL.prompt.md and prints the path
  python scripts/traice_batch.py save BILL FILE      checks FILE (the JSON answer) and saves it; exit 1 if a citation fails
  python scripts/traice_batch.py queue BILL [BILL…]  adds bills to the workspace queue
  python scripts/traice_batch.py prompt BILL compaire   CompAIre's prompt (needs the bill's saved TrAIce run)
  python scripts/traice_batch.py save BILL FILE compaire  checks and saves a CompAIre answer (data/agent_runs/BILL/compaire.json)
"""
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from agents import traice  # noqa: E402

RUNS = ROOT / "data" / "agent_runs"
QUEUE = RUNS / "queue.txt"
TMP = ROOT / "runs_tmp"
PILOT = "Government organization and mandates"


def _rows():
    from pipeline import catalogue
    return {r["id"]: r for r in catalogue.build()}


def _traice_out(bid):
    """The bill's TrAIce output as the site shows it (Claude's saved run, completed by the rule draft)."""
    from agents.research import evidence_pack
    from pipeline import policy
    from pipeline.compare import load
    b = load()[0][bid]
    row = _rows().get(bid) or {}
    draft = traice.rule_draft(bid, evidence_pack(bid), row, policy.context({"title": b["title"], "congress": b["congress"]}), row.get("type", ""))
    return traice.normalize((traice.saved_ai(bid) or {}).get("output"), bid, draft)


def done(bid):
    return (RUNS / bid / "traice.json").exists()


def queued():
    return [x.strip() for x in QUEUE.read_text().split()] if QUEUE.exists() else []


def pilot(rows):
    from pipeline.compare import load
    bills = load()[0]
    ids = [i for i, r in rows.items() if r.get("type") == PILOT and r.get("reviewable") and i in bills]
    # 20th Congress first, text PDFs before scanned ones, then by bill number (newest first)
    return sorted(ids, key=lambda i: (-int(i.split("-")[1]), bills[i].get("text_source") != "pdf_text",
                                      i.split("-")[0], -int(i.split("-")[2])))


def pending(rows):
    q = [i for i in dict.fromkeys(queued()) if not done(i)]
    return q + [i for i in pilot(rows) if not done(i) and i not in q]


def main(argv):
    cmd = argv[1] if len(argv) > 1 else "status"
    if cmd == "status":
        rows = _rows()
        p = pilot(rows)
        print(json.dumps({"pilot_total": len(p), "pilot_done": sum(done(i) for i in p),
                          "workspace_queue_pending": sum(1 for i in queued() if not done(i)),
                          "all_saved_runs": len(list(RUNS.glob("*/traice.json")))}))
    elif cmd == "next":
        n = int(argv[2]) if len(argv) > 2 else 12
        print("\n".join(pending(_rows())[:n]))
    elif cmd == "prompt" and len(argv) > 3 and argv[3] == "compaire":
        from agents import compaire
        bid = argv[2]
        system, user, _ = compaire.build_messages(bid, _traice_out(bid))
        TMP.mkdir(exist_ok=True)
        out = TMP / f"{bid}.compaire.prompt.md"
        out.write_text(f"# SYSTEM PROMPT\n\n{system}\n\n# USER MESSAGE\n\n{user}\n")
        print(out)
    elif cmd == "save" and len(argv) > 4 and argv[4] == "compaire":
        from agents import compaire
        bid, path = argv[2], argv[3]
        out = json.loads(Path(path).read_text())
        if out.get("target") != bid:
            sys.exit(f"target is {out.get('target')!r}, expected {bid}")
        checks = compaire.check_output(out)
        bad = [c for c in checks if c.get("check") != "verified"]
        if bad:
            print(json.dumps([{k: c.get(k) for k in ("section", "check", "quote")} for c in bad], ensure_ascii=False, indent=1))
            sys.exit(f"{len(bad)} of {len(checks)} checks failed; fix or remove them and save again")
        g = compaire.grade(bid, compaire.normalize(out, bid, {}), checks)
        (RUNS / bid).mkdir(parents=True, exist_ok=True)
        (RUNS / bid / "compaire.json").write_text(json.dumps({"output": out, "checks": checks, "meta": {
            "prepared_by": "Claude (scheduled CompAIre run under the owner's Claude subscription)",
            "prompt_version": compaire.PROMPT_VERSION, "grade": g["grade"],
            "time": datetime.now(timezone.utc).isoformat(timespec="seconds")}}, ensure_ascii=False, indent=1))
        print(f"saved CompAIre {bid}: {len(checks)} checks passed; grade {g['grade']} ({g['label']})")
    elif cmd == "prompt":
        from agents.research import build_messages
        bid = argv[2]
        system, user, _ = build_messages(bid, row=_rows().get(bid))
        TMP.mkdir(exist_ok=True)
        out = TMP / f"{bid}.prompt.md"
        out.write_text(f"# SYSTEM PROMPT\n\n{system}\n\n# USER MESSAGE\n\n{user}\n")
        print(out)
    elif cmd == "save":
        from agents.research import check_output
        bid, path = argv[2], argv[3]
        out = json.loads(Path(path).read_text())
        if out.get("target") != bid:
            sys.exit(f"target is {out.get('target')!r}, expected {bid}")
        out["related"] = [r for r in out.get("related", []) if r.get("relationship") not in (traice.LABELS[5], traice.LABELS[6])]
        out["existing_law_overlaps"] = [x for x in out.get("existing_law_overlaps", []) if x.get("label") != traice.LAW_LABELS[3]]
        checks = check_output(out)
        bad = [c for c in checks if c.get("check") != "verified"]
        if bad:
            print(json.dumps([{k: c.get(k) for k in ("section", "check", "quote")} for c in bad], ensure_ascii=False, indent=1))
            sys.exit(f"{len(bad)} of {len(checks)} citations failed; fix or remove them and save again")
        g = traice.grade(bid, dict(out, source="ai"), checks)
        (RUNS / bid).mkdir(parents=True, exist_ok=True)
        (RUNS / bid / "traice.json").write_text(json.dumps({"output": out, "checks": checks, "meta": {
            "prepared_by": "Claude (scheduled TrAIce run under the owner's Claude subscription)",
            "prompt_version": traice.PROMPT_VERSION, "grade": g["grade"],
            "time": datetime.now(timezone.utc).isoformat(timespec="seconds")}}, ensure_ascii=False, indent=1))
        if bid in queued():
            QUEUE.write_text("\n".join(i for i in queued() if i != bid) + "\n")
        print(f"saved {bid}: {len(checks)} citations verified; grade {g['grade']} ({g['label']})")
    elif cmd == "queue":
        q = queued() + [i for i in argv[2:] if i not in queued() and not done(i)]
        RUNS.mkdir(parents=True, exist_ok=True)
        QUEUE.write_text("\n".join(q) + "\n")
        print(f"{len(q)} in the workspace queue")
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv)
