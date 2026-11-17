"""One evidence grade for each agent's output, computed by code (never by the agent).

Every agent is graded on four tests worth 2 points each (8 points):
  1. Bill text: read from the official PDF (2), recognized from a scanned PDF (1), not available (0).
  2. Preparation and verification: prepared by Claude with every cited passage found in its section (2), 80% or more (1);
     drafted by ActCheck's rules without AI (1); fewer verified (0).
  3. Coverage: how much of the agent's mapping rests on full texts rather than titles
     (TrAIce: related measures read in full; CompAIre: design comparisons made against a comparator's full section):
     75% or more (2), 40% or more (1), less (0).
  4. Open points: points the reviewer must still confirm: up to 2 (2), up to 5 (1), more (0).
Grades: A Strong (7-8), B Moderate (5-6), C Limited (3-4), D Weak (0-2). Outputs not prepared by Claude are capped at B.
"""
from html import escape

GRADES = [(7, "A", "Strong"), (5, "B", "Moderate"), (3, "C", "Limited"), (0, "D", "Weak")]

METHOD = [
    "Every agent output gets one evidence grade, computed by ActCheck's code, never by the agent itself.",
    "Four tests, 2 points each: how the bill's text was read (official PDF 2, scanned copy 1); how the findings were prepared and "
    "verified (by Claude with every cited passage found in its section 2, 80% or more 1, ActCheck's draft 1); how much of the mapping "
    "rests on full texts rather than titles (75% or more 2, 40% or more 1); and how many points remain to confirm (up to 2: 2 points, "
    "up to 5: 1 point).",
    "A Strong (7-8 points), B Moderate (5-6), C Limited (3-4), D Weak (0-2). ActCheck's drafts are capped at B until Claude has "
    "prepared and cited the findings.",
    "The note under the final checklist item shows the grade and what kept it from more points; for B or lower, the reviewer verifies "
    "those items against the House or Senate record or the bill PDF before ticking.",
]


def text_test(text_source):
    if text_source == "pdf_text":
        return 2, ""
    if text_source == "ocr":
        return 1, "Bill text recognized from a scanned PDF, so wording may contain reading errors"
    return 0, "Full text of the bill not available"


def prep_test(kind, checks):
    if kind == "rules":
        return 1, "Draft prepared by ActCheck; not yet prepared by Claude"
    if kind == "ai-v2":
        return 1, "Partly prepared by an earlier agent version; other parts drafted by ActCheck"
    n = len(checks or [])
    ok = sum(1 for c in (checks or []) if c.get("check") == "verified")
    if n and ok == n:
        return 2, ""
    if n and ok / n >= 0.8:
        return 1, f"{ok} of {n} cited passages verified"
    return 0, (f"Only {ok} of {n} cited passages verified" if n else "No citations could be checked")


def share_test(full, total, what, none_note):
    if not total:
        return 1, none_note
    share = full / total
    pts = 2 if share >= 0.75 else 1 if share >= 0.4 else 0
    return pts, ("" if pts == 2 and full == total else f"{full} of {total} {what}")


def open_test(n, where="For checking"):
    pts = 2 if n <= 2 else 1 if n <= 5 else 0
    return pts, ("" if pts == 2 else f"{n} points to confirm (see {where})")


def finish(tests, kind):
    pts = sum(t[0] for t in tests)
    notes = [t[1] for t in tests if t[1]]
    if kind != "ai" and pts > 6:
        pts = 6
        notes.append("Capped at B until Claude has reviewed and cited the findings")
    g = next(x for x in GRADES if pts >= x[0])
    return {"grade": g[1], "label": g[2], "points": pts, "of": 2 * len(tests), "to_note": notes,
            "reasons": notes}


def note_html(gr, agent):
    notes = gr.get("to_note") or []
    body = "; ".join(notes) + "." if notes else "Nothing to note."
    return (f'<div class="ac-grade g{gr["grade"]}"><div class="gh"><span class="gl">{gr["grade"]}</span>'
            f'<b>{escape(agent)} evidence grade: {gr["label"]}</b> · {gr["points"]} of {gr["of"]} points</div>'
            f'<div class="gw"><b>To note:</b> {escape(body)}</div></div>')
