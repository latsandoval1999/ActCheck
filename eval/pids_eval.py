"""Score an ActCheck review of HB 6789 against an independent expert comment (held-out benchmark).

Benchmark: PIDS, "Comments on the Bills Proposing to Establish a National Framework for Water Resource Management
and Make Institutional Rearrangements in the Water Sector (SBs 83, 145, 225, 240, 310, 426, 1080, 1475 and HB 6789)",
prepared by A. M. Navarro, 9 March 2026. Its points are paraphrased in eval/pids_hb6789.csv.

HELD OUT: the PIDS comment is never given to the agents (tests/test_benchmark.py checks this), so it measures
whether ActCheck independently surfaces what an expert reviewer raised. Keyword matching is a first pass; the
reviewer confirms each match by reading the output.

    python -m eval.pids_eval --runs logs/p3_runs.jsonl          # latest ApprAIsal run on HB-20-6789
    python -m eval.pids_eval --file my_review.json               # any saved output (JSON or text)
"""
import argparse
import csv
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BILL = "HB-20-6789"


def points():
    with open(ROOT / "eval" / "pids_hb6789.csv", newline="") as f:
        return list(csv.DictReader(f))


def covered(text, keywords):
    """A point counts as covered when every ';'-separated group has at least one '|' alternative in the text."""
    t = text.lower()
    return all(any(re.search(re.escape(k.strip()), t) for k in g.split("|")) for g in keywords.split(";"))


def score(text):
    rows = []
    for p in points():
        rows.append({**p, "covered": covered(text, p["keywords"])})
    rel = [r for r in rows if r["applies_to_hb6789"] == "yes"]
    return {"covered": sum(r["covered"] for r in rel), "of": len(rel), "rows": rows}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs")
    ap.add_argument("--file")
    a = ap.parse_args()
    if a.file:
        text = Path(a.file).read_text()
    else:
        out = None
        for line in open(a.runs or ROOT / "logs" / "p3_runs.jsonl"):
            r = json.loads(line)
            if r.get("target") == BILL or r.get("bill") == BILL:
                out = r.get("output")
        if out is None:
            raise SystemExit(f"No run on {BILL} in the log yet. Run ApprAIsal (and TrAIce, CompAIre) on {BILL} first.")
        text = json.dumps(out, ensure_ascii=False)
    s = score(text)
    for r in s["rows"]:
        flag = "covered" if r["covered"] else "missing"
        print(f"{r['id']} [{flag}{'' if r['applies_to_hb6789'] == 'yes' else ', Senate bills only'}] {r['point']}")
    print(f"\nPIDS points relevant to HB 6789 surfaced by ActCheck: {s['covered']} of {s['of']}")


if __name__ == "__main__":
    main()
