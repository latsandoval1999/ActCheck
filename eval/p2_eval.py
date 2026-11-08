"""Score Agent 2 against eval/p2_truth.csv.

    python -m eval.p2_eval --runs logs/p2_runs.jsonl

verdict_ok   -- the overall verdict matches
diff_recall  -- share of expected differences found (same category, citing the expected section)
Only pairs the agent was run on are scored.
"""
import argparse
import csv
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", required=True)
    a = ap.parse_args()
    runs = {}
    for line in open(a.runs):
        r = json.loads(line)
        runs[(r["target"], r["reference"])] = r["output"]
    truth = [t for t in csv.DictReader(open(ROOT / "eval" / "p2_truth.csv")) if (t["target"], t["reference"]) in runs]
    if not truth:
        raise SystemExit("None of the run pairs are in eval/p2_truth.csv yet.")
    tot_exp = tot_hit = v_ok = 0
    for t in truth:
        out = runs[(t["target"], t["reference"])]
        exp = [e.split("@") for e in t["expected_differences"].split(";") if e]
        got = {(d.get("category"), d.get("target_section")) for d in out.get("differences", [])} | \
              {(d.get("category"), d.get("reference_section")) for d in out.get("differences", [])}
        got_secs = {s for _, s in got}
        hits = [e for e in exp if (e[0], e[1]) in got or e[1] in got_secs]
        ok = out.get("verdict", "") == t["verdict"]
        v_ok += ok
        tot_exp += len(exp)
        tot_hit += len(hits)
        print(f"{t['target']} vs {t['reference']}: verdict {out.get('verdict')!r} (expected {t['verdict']!r}) "
              f"{'OK' if ok else 'DIFFERENT'}; differences found {len(hits)}/{len(exp)}")
        for e in exp:
            print(f"   {'found ' if e in hits else 'MISSED'} {e[0]} @ {e[1]}")
    print(f"\nverdict correct {v_ok}/{len(truth)}; expected differences found {tot_hit}/{tot_exp}"
          + (f" ({tot_hit / tot_exp:.0%})" if tot_exp else ""))


if __name__ == "__main__":
    main()
