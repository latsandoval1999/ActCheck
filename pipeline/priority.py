"""Bills recommended for review: a transparent score, computed by rules (no AI), for pending 20th Congress bills
that have a full text. It shows the reviewer where DBM comments are most needed first; it does not decide anything.

Points (the reasons are shown with each bill):
  Stage, how soon the bill may move without DBM comments: sent to the President or in the bicameral conference 4;
      second reading or plenary 3; in the committee 1.
  Strategic priority: one of the 44 LEDAC Common Legislative Agenda measures 3; a FY 2027 Budget Priorities
      Framework area (by title) 1.
  Fiscal and organizational weight: creates a national agency 2; appropriates funds (title) 1.
  Duplication and consolidation: three or more pending bills with the same title 1.
  Public reports received on the bill: 1 each, up to 2.
Bills with the same title are listed once, by the first filed.
"""
import re

from pipeline.policy import BPF_AREAS

STAGE = {"Sent to the President": 4, "In Congress (bicameral conference)": 4, "Second reading": 3,
         "In the House of Representatives": 3, "In the committee": 1}
METHOD = [
    ("Stage", "sent to the President or bicameral conference 4; second reading or plenary 3; in the committee 1"),
    ("Strategic priority", "LEDAC Common Legislative Agenda measure 3; FY 2027 Budget Priorities Framework area 1"),
    ("Fiscal and organizational weight", "creates a national agency 2; appropriates funds 1"),
    ("Duplication", "three or more pending bills with the same title 1"),
    ("Public reports", "1 for each report received, up to 2"),
]


def _norm(t):
    return re.sub(r"[^A-Z ]", "", (t or "").upper())[:120]


def rank(cat, report_counts=None, n=20):
    """Top n pending 20th Congress bills with full text, with score and reasons (a pandas DataFrame)."""
    report_counts = report_counts or {}
    df = cat[(cat["congress"] == "20") & (cat["status_group"] == "PENDING") & (cat["reviewable"])].copy()
    same = df["title"].map(_norm).map(df["title"].map(_norm).value_counts())
    scores, whys = [], []
    for (_, r), k in zip(df.iterrows(), same):
        pts, why = 0, []
        s = STAGE.get(r["status_sub"], 0)
        if s:
            pts += s
            why.append({4: "at the final stage (" + r["status_sub"].lower() + ")", 3: "on the floor (" + r["status_sub"].lower().replace("in the ", "") + ")",
                        1: "in the committee"}[s])
        if r.get("ledac"):
            pts += 3
            why.append("LEDAC priority")
        areas = [a for a, _, rx in BPF_AREAS if re.search(rx, r["title"] or "", re.I)]
        if areas:
            pts += 1
            why.append("FY 2027 budget priority: " + areas[0].lower())
        if r["scope"].startswith("Creates a national agency"):
            pts += 2
            why.append("creates a national agency")
        if re.search(r"APPROPRIATING FUNDS", r["title"] or "", re.I):
            pts += 1
            why.append("appropriates funds")
        if k >= 3:
            pts += 1
            why.append(f"{k - 1} other bills with the same title (likely consolidation)")
        c = min(2, report_counts.get(r["id"], 0))
        if c:
            pts += c
            why.append(f"{report_counts[r['id']]} public report{'s' if report_counts[r['id']] > 1 else ''}")
        scores.append(pts)
        whys.append(why)
    df["priority"], df["why"] = scores, whys
    df["_n"] = df["number"].astype(int)
    df["_t"] = df["title"].map(_norm)
    df["similar"] = (same - 1).astype(int)
    # bills with the same title are listed once: the first filed stands for the group
    df = df.sort_values("_n").drop_duplicates("_t", keep="first")
    return df.sort_values(["priority", "_n"], ascending=[False, True]).head(n).drop(columns=["_n", "_t"]).reset_index(drop=True)
