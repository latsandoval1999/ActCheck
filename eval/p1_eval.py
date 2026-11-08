"""Score Agent 1 (or the baseline) against the answer key in eval/p1_truth.csv.

    python -m eval.p1_eval              # baseline (no AI)
    python -m eval.p1_eval --runs logs/p1_runs.jsonl   # agent outputs saved from the app

Metrics (for the portfolio's Section 7):
  found      -- the related document appears in the output at all (recall)
  label_ok   -- and the relationship label matches the answer key
Add rows to p1_truth.csv as you confirm more relationships (mark confirmed_by_reviewer).
"""
import argparse
import csv
import json
from pathlib import Path

from agents.research import evidence_pack

ROOT = Path(__file__).resolve().parents[1]


def norm(label):
    label = (label or "").lower()
    for key in ("consolidated", "near-copy", "earlier version", "other chamber", "competing", "existing law", "unrelated"):
        if key in label:
            return key
    return label


def baseline_output(target):
    pack = evidence_pack(target)
    out = {r["id"]: r["baseline_label"] for r in pack["related"]}
    out.update({l["law"]: "existing law affected" for l in pack["laws"]})
    return out


def agent_outputs(path):
    res = {}
    for line in open(path):
        r = json.loads(line)
        o = r.get("output", {})
        d = {x.get("id"): x.get("relationship") for x in o.get("related", [])}
        d.update({x.get("law"): "existing law affected" for x in o.get("existing_law_overlaps", [])})
        res[o.get("target") or r.get("target")] = d
    return res


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", help="JSONL of saved agent outputs")
    a = ap.parse_args()
    truth = list(csv.DictReader(open(ROOT / "eval" / "p1_truth.csv")))
    agent = agent_outputs(a.runs) if a.runs else None
    if agent is not None:  # score only the bills the agent was actually run on
        truth = [t for t in truth if t["target"] in agent]
        if not truth:
            raise SystemExit("None of the run targets are in eval/p1_truth.csv yet.")
    rows, found, ok = [], 0, 0
    cache = {}
    for t in truth:
        if agent is not None:
            pred = agent.get(t["target"], {})
        else:
            pred = cache.setdefault(t["target"], baseline_output(t["target"]))
        got = pred.get(t["related"])
        f = got is not None
        l_ok = f and norm(got) == norm(t["relationship"])
        found += f
        ok += l_ok
        rows.append((t["target"], t["related"], t["relationship"], got or "-", "yes" if f else "no", "yes" if l_ok else "no"))
    w = max(len(r[3]) for r in rows)
    print(f"{'target':<12} {'related':<12} {'expected':<34} {'predicted':<{w}} found label_ok")
    for r in rows:
        print(f"{r[0]:<12} {r[1]:<12} {r[2]:<34} {r[3]:<{w}} {r[4]:<5} {r[5]}")
    n = len(truth)
    print(f"\n{'agent' if agent else 'baseline'}: found {found}/{n} ({found / n:.0%}), correct label {ok}/{n} ({ok / n:.0%})")


if __name__ == "__main__":
    main()
