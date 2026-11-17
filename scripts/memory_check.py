"""Memory budget check for the hosted portal (Streamlit Community Cloud allows about 1 GB; the app was restricted
on 17 Nov 2026 after the corpus grew past it). Loads what the portal loads and runs the heaviest analyses once,
then fails if the peak memory or the corpus size is over budget. Run by the tests and before every daily commit.

    python scripts/memory_check.py        -> exit 1 if over budget
"""
import json
import resource
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
BUDGET_MB = 700          # leaves room for Streamlit itself and several visitors under the ~1 GB limit
SECTIONS_MB = 70         # size of data/processed/sections.jsonl on disk


def peak_mb():
    return resource.getrusage(resource.RUSAGE_SELF).ru_maxrss / 1024


def main():
    problems = []
    size = (ROOT / "data" / "processed" / "sections.jsonl").stat().st_size / 1e6
    if size > SECTIONS_MB:
        problems.append(f"sections.jsonl is {size:.0f} MB (budget {SECTIONS_MB} MB)")
    from pipeline.build_corpus import MAX_SECTION, MAX_DOC, CUT_NOTE
    per_doc = {}
    for line in open(ROOT / "data" / "processed" / "sections.jsonl"):
        s = json.loads(line)
        if len(s["text"]) > MAX_SECTION + len(CUT_NOTE):
            problems.append(f"{s['id']} has {len(s['text']):,} characters")
        per_doc[s["bill"]] = per_doc.get(s["bill"], 0) + len(s["text"])
    problems += [f"{b} has {n:,} characters of sections" for b, n in per_doc.items() if n > MAX_DOC + 2 * MAX_SECTION]
    t = time.time()
    from pipeline import compare, catalogue
    import pandas as pd
    compare.load()
    pd.DataFrame(catalogue.build())
    probe = next((b for b in ("HB-20-6789", "HB-20-2322") if b in compare.load()[0]), next(iter(compare.load()[0])))
    rel = compare.related_bills(probe, top=5)
    if rel:
        compare.align(probe, rel[0]["id"])
    from agents.research import evidence_pack
    evidence_pack(probe)
    peak = peak_mb()
    print(f"peak memory {peak:.0f} MB (budget {BUDGET_MB} MB); sections.jsonl {size:.0f} MB; {time.time() - t:.0f} s")
    if peak > BUDGET_MB:
        problems.append(f"peak memory {peak:.0f} MB is over the {BUDGET_MB} MB budget")
    for p in problems[:20]:
        print("OVER BUDGET:", p)
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
