"""ActCheck: an agentic AI system for Philippine legislative review.

    streamlit run app/streamlit_app.py

Pages: Home (summary data, bill typology, how a review flows) -> Bills (every bill; Type and Status
filters; click a title for details; Review sends it to the workspace) -> Review workspace (bills under
review; Step 1 TrAIce, Step 2 CompAIre, Step 3 AppraisAI, each with a run button and a reviewer
checklist that unlocks the next step; comments and report; DBM-format memo and letter) -> Library ->
Run log -> How it Works. BILLy, the review companion, floats in the corner of every page.

Without an API key, every rules-only part works, BILLy answers in search mode, and each agent step has
a free route (download the prompt, run it in a Claude chat, paste the reply back to check and save it).
"""
import json
import sys
from html import escape
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "app"))

# Streamlit re-runs this file but keeps imported helper modules in memory; when new code is deployed,
# drop the project's modules so every page uses the current version.
_code_stamp = max(p.stat().st_mtime for d in ("app", "agents", "pipeline") for p in (ROOT / d).glob("*.py"))
if getattr(sys, "_actcheck_stamp", None) != _code_stamp:
    for _m in [m for m in sys.modules if m.split(".")[0] in ("agents", "pipeline", "ui", "render", "howitworks")]:
        del sys.modules[_m]
    sys._actcheck_stamp = _code_stamp

from agents import llm, store, documents as docs  # noqa: E402
from agents.names import APP_NAME, AGENT1, AGENT2, AGENT3  # noqa: E402
from pipeline import catalogue, typology  # noqa: E402
from pipeline.compare import load, related_bills  # noqa: E402
import render  # noqa: E402
import ui  # noqa: E402

SUBHEADING = "An Agentic AI System for Philippine Legislative Review"
TAGLINE = "Trace the bill. Spot the changes. Weigh the impact."
DESCRIPTION = ("A tool to aid government analysts to trace a bill's history, see what changed, and assess its legal and budget "
               "implications in order to provide comments for legislators.")
LABEL = "AI-assisted preliminary draft for DBM reviewer validation. Not an official position."
PILOT = "Creates a national agency (pilot)"
PAGES = ["Home", "Bills", "Review workspace", "Library", "Run log", "How it Works"]
STEPS = ["Trace", "Compare", "Weigh", "Comments & report", "Memo & letter"]

st.set_page_config(page_title=f"{APP_NAME} · {SUBHEADING}", page_icon=str(ROOT / "app" / "static" / "favicon.png"),
                   layout="wide", initial_sidebar_state="collapsed")
ui.inject()
bills, secs = load()


@st.cache_data(show_spinner="Loading the bill list...")
def bill_table(stamp):
    return pd.DataFrame(catalogue.build(stamp))


# The rules-only analyses take a few seconds each; cache them per bill (the stamp changes when the corpus does).
@st.cache_data(show_spinner="Gathering the evidence...", max_entries=64)
def c_evidence(bid, stamp):
    from agents.research import evidence_pack
    return evidence_pack(bid)


@st.cache_data(show_spinner="Finding related bills...", max_entries=64)
def c_related(bid, stamp):
    return related_bills(bid, top=15)


@st.cache_data(show_spinner="Comparing the bills...", max_entries=64)
def c_compare(bid, ref, stamp):
    from agents.diagnosis import report_markdown
    return report_markdown(bid, ref)


@st.cache_data(show_spinner=False, max_entries=64)
def c_cost(bid, stamp):
    from agents.costing import cost_range
    return cost_range(bid)


# ---------------- navigation ----------------
def go(page, bill=None):
    """Navigate on the next run (widget state can only be changed before widgets are drawn)."""
    if bill:
        st.session_state["bill"] = bill
    st.session_state["_goto"] = page
    st.rerun()


qp_page = st.query_params.get("page")
if qp_page in PAGES:
    st.session_state["_goto"] = qp_page
    del st.query_params["page"]
if "_goto" in st.session_state:
    st.session_state["nav"] = st.session_state.pop("_goto")
if st.session_state.get("nav") not in PAGES:
    st.session_state["nav"] = "Home"

with st.sidebar:
    st.markdown("### Reviewer settings")
    pasted = st.text_input("Anthropic API key (optional, kept for this session only)", type="password")
    if pasted:
        st.session_state["user_api_key"] = pasted
    live = bool(llm.api_key())
    st.write("AI agents:", "**on**" if live else "**off**: rules-only checks, BILLy in search mode, free route for each agent")
    st.caption(LABEL)

ui.masthead(APP_NAME, SUBHEADING)
page = st.radio("Navigation", PAGES, key="nav", horizontal=True, label_visibility="collapsed")
cat = bill_table(catalogue.stamp())


def watch_state():
    p = ROOT / "data" / "watch" / "state.json"
    return json.loads(p.read_text()) if p.exists() else {}


def row_of(bid):
    r = cat[cat["id"] == bid]
    return r.iloc[0].to_dict() if len(r) else None


def house_note(row):
    if row and row.get("house_origin"):
        return "Must originate in the House (Const. Art. VI, Sec. 24)"
    return ""


def free_route(key, prompt_fn, on_reply, json_reply=True):
    """Download the prompt, run it in a Claude chat, paste the reply back."""
    with st.expander("No API key? Free route: run this step in a Claude chat"):
        st.caption("1) Download the prompt. 2) Attach it to a new Claude chat and ask it to follow the SYSTEM PROMPT and reply "
                   + ("with the JSON only." if json_reply else "with the document only.") + " 3) Paste the reply here.")
        try:
            system, user = prompt_fn()
            st.download_button("Download prompt", f"=== SYSTEM PROMPT ===\n{system}\n=== USER MESSAGE ===\n{user}",
                               file_name=f"prompt_{key}.txt", key=f"dl_{key}")
        except Exception as e:
            st.info(str(e))
            return
        reply = st.text_area("Paste the reply", key=f"reply_{key}", height=140)
        if st.button("Check and save reply", key=f"save_{key}", disabled=not reply.strip()):
            try:
                on_reply(llm.parse_json(reply) if json_reply else reply)
                st.success("Checked and saved.")
                st.rerun()
            except Exception as e:
                st.error(f"Could not read the reply: {e}")


# ---------------- Bills: review action and details dialog ----------------
def start_review(row):
    """Send a bill to the review workspace; fetch its text first if ActCheck does not have it yet."""
    if not row["reviewable"]:
        with st.spinner(f"Fetching the text of {row['label']} from its source..."):
            from pipeline import ondemand
            ok, msg = ondemand.fetch(row)
        if not ok:
            st.error(f"Could not open {row['label']} for review: {msg}.")
            return
        st.cache_data.clear()
    store.queue(row["id"])
    go("Review workspace", row["id"])


@st.dialog("Bill details", width="large")
def bill_dialog(row):
    st.markdown(f"### {escape(row['label'])} · {row['congress']}th Congress")
    ui.badges([(row["bill_type"], "navy"), (row["type"], "gold"), (row["applies_to"], ""), (row["status"], ""),
               ("Full text in ActCheck" if row["reviewable"] else "Listing only", "green" if row["reviewable"] else ""),
               (house_note(row), "red")])
    ui.html(f'<div class="ac-billtitle">{escape(row["title"] or row["short_title"] or "(title not yet available)")}</div>')
    meta = [("Short title", row["short_title"]), ("Filed", row["date_filed"]), ("Committee", row["committee"]),
            ("Author", row["author"]), ("Listed from", row["source"])]
    st.caption(" · ".join(f"{k}: {v}" for k, v in meta if v))
    st.caption("Type and 'applies to' are classified from the title by rules; confirm them during review.")
    c1, c2 = st.columns(2)
    if c1.button("Review this bill", type="primary", key=f"dlg_rev_{row['id']}"):
        start_review(row)
    if row["source_url"]:
        c2.link_button("View bill (source document)", row["source_url"])


# ---------------- Review workspace helpers ----------------
def checklist(bid, step, items, heading="Reviewer checklist: tick every item to unlock the next step"):
    """Salient checklist with a note and file upload per item. Returns True when every item is ticked."""
    rec = store.load(bid)
    allcl = rec.get("checklist") or {}
    cl = dict(allcl.get(step) or {})
    with st.container(key=f"chk_{step}"):
        ui.html(f'<div class="ac-check"><div class="ac-check-h">✓ {escape(heading)}</div></div>')
        changed = False
        for i, item in enumerate(items):
            cur = cl.get(str(i), {"done": False, "note": "", "files": []})
            done = st.checkbox(item, value=cur.get("done", False), key=f"ck_{bid}_{step}_{i}")
            with st.expander("Add a note or attach a file" + (f" · {len(cur.get('files', []))} file(s)" if cur.get("files") else "")
                             + (" · note added" if cur.get("note") else "")):
                note = st.text_area("Note", value=cur.get("note", ""), key=f"nt_{bid}_{step}_{i}", height=70,
                                    label_visibility="collapsed", placeholder="Comment or finding for this item")
                up = st.file_uploader("Attach a file", key=f"up_{bid}_{step}_{i}", label_visibility="collapsed")
                files = list(cur.get("files", []))
                if up is not None and not any(f.endswith(up.name.replace(" ", "_")) for f in files):
                    files.append(store.save_upload(bid, f"{step}-{i}", up.name, up.getvalue()))
                for f in files:
                    st.caption(f"📎 {f}")
            new = {"done": done, "note": note, "files": files}
            if new != cur:
                cl[str(i)] = new
                changed = True
        if changed:
            allcl[step] = cl
            store.save(bid, "checklist", allcl, trail=False)
            st.rerun()                       # refresh so the step locks and the progress bar reflect the change
        n_done = sum(1 for i in range(len(items)) if (cl.get(str(i)) or {}).get("done"))
        st.caption(f"{n_done} of {len(items)} items done.")
    return n_done == len(items) and len(items) > 0


CHECK1 = ["The related bills and how each relates (earlier version, counterpart, refiled) are correct.",
          "Every citation flagged 'needs checking' has been checked against the bill PDF.",
          "The existing laws and agencies the bill overlaps with are confirmed."]
CHECK2 = ["The reference measure is the right comparison for this bill.",
          "Each substantial difference and its cost effect has been checked against both texts.",
          "The design options DBM may comment on are noted."]


def pick_reference(bid, research_out):
    order = ("consolidated", "counterpart", "near-copy", "earlier version", "competing")
    if research_out:
        for lab in order:
            for r in research_out.get("related", []):
                if lab in (r.get("relationship") or "") and r.get("id") in bills and r["id"] != bid:
                    return r["id"]
    rel = c_related(bid, catalogue.stamp())
    return rel[0]["id"] if rel else None


def paper(fields, kind):
    """On-screen preview of the memo or letter in the DBM layout (Tahoma)."""
    e = lambda s: escape(str(s or "")).replace("\n", "<br>")  # noqa: E731
    head = ('<div style="text-align:center;font-size:.7rem;color:#888;font-style:italic">[Insert official DBM letterhead and seal]</div>'
            '<div style="text-align:center;font-size:.8rem">REPUBLIC OF THE PHILIPPINES</div>'
            '<div style="text-align:center;font-weight:700;font-size:1rem;margin-bottom:.8rem">DEPARTMENT OF BUDGET AND MANAGEMENT</div>')
    if kind == "memo":
        rows = "".join(f'<tr><td style="width:70px;vertical-align:top">{lab}</td><td style="width:14px;vertical-align:top">:</td>'
                       f'<td style="{"font-weight:700;" if k == "subject" else ""}text-align:justify">{e(fields.get(k))}</td></tr>'
                       for k, lab in (("thru", "Thru"), ("from_", "From"), ("subject", "Subject")))
        body = "".join(f'<p style="margin:.5rem 0 .2rem"><b>{lab}</b></p><p style="text-align:justify;margin:0 0 0 1.2rem">{e(fields.get(k))}</p>'
                       for k, lab in docs.MEMO_FIELDS[5:])
        inner = (f'<p>{e(fields.get("date"))}</p><p><b>MEMORANDUM FOR {e(fields.get("memo_for"))}</b></p><table style="font-size:.86rem">{rows}</table>'
                 f'<hr style="border:0;border-top:1.5px solid #000">{body}')
    else:
        inner = (f'<p>{e(fields.get("date"))}</p><p><b>{e(fields.get("addressee"))}</b><br>{e(fields.get("office"))}<br>{e(fields.get("address"))}</p>'
                 f'<p><b>Subject: {e(fields.get("subject"))}</b></p><p>{e(fields.get("salutation"))}</p>'
                 + "".join(f'<p style="text-align:justify">{e(fields.get(k))}</p>' for k in ("p1", "p2", "p3", "p4"))
                 + f'<p>{e(fields.get("closing"))}</p>')
    ui.html(f'<div style="font-family:Tahoma,Verdana,sans-serif;font-size:.86rem;background:#fff;border:1px solid #D8D3C7;'
            f'box-shadow:0 2px 10px rgba(0,0,0,.06);padding:1.6rem 2rem;max-width:780px;margin:.4rem auto">{head}{inner}'
            f'<p style="margin-top:1.2rem;font-style:italic">{docs.SIGNATURE}</p><p style="font-size:.7rem;color:#888;font-style:italic">{LABEL}</p></div>')


def field_editor(key, fields, spec):
    # the widget keys carry a fingerprint of the saved text, so the boxes always show the latest saved version
    import hashlib
    rev = hashlib.md5(json.dumps(fields, sort_keys=True).encode()).hexdigest()[:8]
    with st.form(f"{key}_{rev}"):
        new = {}
        for k, lab in spec:
            v = str(fields.get(k, ""))
            new[k] = st.text_area(lab, v, height=68 if len(v) < 120 else 150, key=f"{key}_{k}_{rev}")
        ok = st.form_submit_button("Save edits", type="primary")
    return new if ok else None


def case(bid):
    from agents.research import evidence_pack, build_messages as p1_msgs, check_output as p1_check
    from agents.diagnosis import report_markdown as p2_md, build_messages as p2_msgs, check_output as p2_check
    from agents.costing import cost_range, peso
    from agents.appraisal import (check_review, build_review_messages, build_redteam_messages, build_memo_messages,
                                  build_letter_messages, governance_flags)
    b = bills[bid]
    rec = store.load(bid)
    row = row_of(bid) or {}
    cl = rec.get("checklist") or {}
    ui.html(f'<div class="ac-crumb">Review workspace / <b>{escape(b["label"])}</b></div>')
    st.markdown(f"## {escape(b['label'])} · {b['congress']}th Congress")
    ui.badges([(row.get("bill_type"), "navy"), (row.get("type"), "gold"), (row.get("applies_to"), ""), (row.get("status"), ""),
               (house_note(row), "red")])
    ui.html(f'<div class="ac-billtitle">{escape(b["title"])}</div>')
    research_out = (rec.get("research") or {}).get("output")
    rev = (rec.get("review") or {}).get("output")

    def all_done(step, n):
        c = cl.get(step) or {}
        return n > 0 and all((c.get(str(i)) or {}).get("done") for i in range(n))
    check3 = (rev or {}).get("checklist") or ["Costing assumptions marked 'to verify' are checked.", "The red-team issues are resolved or noted.",
                                               "The preliminary comments are edited and complete."]
    check3 = list(check3[:10]) + ["I have verified this review against the sources and approve it as the basis for the memo."]
    d1, d2, d3 = all_done("s1", len(CHECK1)), all_done("s2", len(CHECK2)), all_done("s3", len(check3))
    d4 = d3 and bool(rec.get("comments"))
    d5 = docs.position_decided(rec.get("memo_fields") or {}) and bool(rec.get("letter_fields"))
    states = []
    for i, d in enumerate([d1, d2, d3, d4, d5]):
        prev = [True, d1, d2, d3, d3][i]
        states.append("done" if d else ("now" if prev else ""))
    ui.progress(STEPS, states)
    st.caption(f"Text: {b['text_source']} ({b['n_sections']} sections)" + (" · OCR text: check quotes against the PDF" if b["text_source"] == "ocr" else "")
               + ("" if live else " · AI agents are off: add a key under Reviewer settings (top-left ›) or use each step's free route."))
    if row.get("type") != "Government organization and mandates":
        ui.notice(f"<b>Outside the pilot scope.</b> {AGENT1} and {AGENT2} work on any bill. {AGENT3}'s costing engine is built for bills that "
                  "create a new agency, so treat its cost range as not applicable here.", "navy")

    # Step 1: TrAIce
    with st.container(border=True):
        ui.step_header(1, AGENT1, "Trace the bill", "done" if d1 else "now")
        ui.html(f'<div class="ac-step-d">Finds the bill\'s earlier versions in past Congresses, its counterpart and refiled copies in both chambers, '
                f'and the existing laws it amends or overlaps with. Every link is cited to a section and the quote is checked automatically.</div>')
        if st.button(f"▶ Run {AGENT1}", type="primary", disabled=not live, key="run1"):
            from agents.research import run_agent as run1
            with st.spinner(f"{AGENT1} is tracing the bill..."):
                r1 = run1(bid)
            store.save(bid, "research", {"output": r1["output"], "checks": r1["checks"]}, f"{AGENT1} run")
            store.set_status(bid, "in review")
            st.rerun()
        free_route(f"p1_{bid}", lambda: p1_msgs(bid)[:2],
                   lambda out: (store.save(bid, "research", {"output": out, "checks": p1_check(out)}, f"{AGENT1} (free route)"),
                                store.set_status(bid, "in review")))
        render.trace(c_evidence(bid, catalogue.stamp()), research_out, (rec.get("research") or {}).get("checks"))
        checklist(bid, "s1", CHECK1)

    # Step 2: CompAIre
    with st.container(border=True):
        ui.step_header(2, AGENT2, "Spot the changes", "done" if d2 else ("now" if d1 else "lock"))
        ui.html('<div class="ac-step-d">Compares the bill with the closest related measure, section by section: the problem it addresses, '
                'the substantial differences (with their likely cost effect) and the design options seen across related bills.</div>')
        if not d1:
            st.caption("🔒 Complete Step 1's checklist to unlock this step.")
        else:
            cand = [r["id"] for r in c_related(bid, catalogue.stamp())]
            default_ref = pick_reference(bid, research_out) or (cand[0] if cand else None)
            if default_ref and default_ref not in cand:
                cand = [default_ref] + cand
            saved_ref = rec.get("reference", default_ref)
            ref = st.selectbox("Compare with", cand, index=cand.index(saved_ref) if saved_ref in cand else 0,
                               format_func=lambda x: f"{bills[x]['label']} ({bills[x]['congress']}th) · {bills[x]['title'][:90]}")
            if st.button(f"▶ Run {AGENT2}", type="primary", disabled=not live, key="run2"):
                from agents.diagnosis import run_agent as run2
                with st.spinner(f"{AGENT2} is comparing the bills..."):
                    r2 = run2(bid, ref)
                store.save(bid, "diagnosis", {"output": r2["output"], "checks": r2["checks"], "reference": ref}, f"{AGENT2} run")
                store.save(bid, "reference", ref)
                st.rerun()
            free_route(f"p2_{bid}_{ref}", lambda: p2_msgs(bid, ref)[:2],
                       lambda out: (store.save(bid, "diagnosis", {"output": out, "checks": p2_check(out, bid, ref), "reference": ref}, f"{AGENT2} (free route)"),
                                    store.save(bid, "reference", ref)))
            dia = rec.get("diagnosis") or {}
            if dia and dia.get("reference") == ref:
                render.compare(dia["output"], dia.get("checks"))
            else:
                render.compare(None, baseline_md=c_compare(bid, ref, catalogue.stamp()))
            checklist(bid, "s2", CHECK2)

    # Step 3: AppraisAI
    with st.container(border=True):
        ui.step_header(3, AGENT3, "Weigh the impact", "done" if d3 else ("now" if d2 else "lock"))
        ui.html('<div class="ac-step-d">Drafts the preliminary review: a first-year cost range from the rules-based costing engine (salary schedule '
                'and comparator agencies), implementation risks, overlaps and preliminary comments. A separate red-teamer then checks the draft.</div>')
        if not d2:
            st.caption("🔒 Complete Step 2's checklist to unlock this step.")
        else:
            dia_out = (rec.get("diagnosis") or {}).get("output")
            if st.button(f"▶ Run {AGENT3} (with red-team check)", type="primary", disabled=not live, key="run3"):
                from agents.appraisal import run_review, run_redteam
                with st.spinner(f"{AGENT3} is weighing the impact, then the red-teamer checks it..."):
                    r3 = run_review(bid, research_out, dia_out)
                    store.save(bid, "review", {"output": r3["draft"], "checks": r3["checks"]}, f"{AGENT3} review")
                    rt = run_redteam(bid, r3["draft"])
                    store.save(bid, "redteam", {"output": rt["redteam"]}, "Red-team run")
                st.rerun()
            free_route(f"p3review_{bid}", lambda: build_review_messages(bid, research_out, dia_out)[:2],
                       lambda out: store.save(bid, "review", {"output": out, "checks": check_review(bid, out)}, f"{AGENT3} review (free route)"))
            if rev:
                free_route(f"p3rt_{bid}", lambda: build_redteam_messages(bid, rev),
                           lambda out: store.save(bid, "redteam", {"output": out}, "Red-team (free route)"))
            render.appraise(rev, c_cost(bid, catalogue.stamp()), peso, check_review(bid, rev) if rev else None, (rec.get("redteam") or {}).get("output"))
            if not rev:
                st.caption(f"{AGENT3} has not drafted a review yet. The checklist below can still be completed from the rules-only analysis.")
            done3 = checklist(bid, "s3", check3, "Reviewer checklist: verify, then approve to unlock comments, memo and letter")
            if done3 and not rec.get("approved_review"):
                store.save(bid, "approved_review", rev or {"summary": b["title"]}, "Reviewer approved the review")
                store.set_status(bid, "review approved")
                st.rerun()

    # Step 4: comments and report
    with st.container(border=True):
        ui.step_header(4, "Comments & report", "Edit and export", "done" if d4 else ("now" if d3 else "lock"))
        if not d3:
            st.caption("🔒 Approve the review in Step 3 to unlock.")
        else:
            from agents.report import markdown as rep_md, docx_bytes
            comments = rec.get("comments") or [dict(c, include=True) for c in (rev or {}).get("preliminary_comments", [])]
            ui.html('<div class="ac-step-d">Edit the wording, untick to drop a comment, or add rows. Saved comments go into the report, the memo and the letter.</div>')
            cdf = pd.DataFrame(comments or [{"include": True, "comment": "", "section": "", "basis": ""}])
            ed = st.data_editor(cdf[[c for c in ("include", "comment", "section", "basis") if c in cdf]], num_rows="dynamic",
                                use_container_width=True, key=f"ed_{bid}",
                                column_config={"include": st.column_config.CheckboxColumn("Include", width="small"),
                                               "comment": st.column_config.TextColumn("Comment", width="large"),
                                               "section": st.column_config.TextColumn("Section", width="small")})
            c1, c2, c3 = st.columns(3)
            if c1.button("Save comments", type="primary"):
                store.save(bid, "comments", ed.fillna("").to_dict("records"), "Reviewer edited comments")
                st.rerun()
            c2.download_button("Download report (Word)", docx_bytes(bid), file_name=f"ActCheck_preliminary_report_{bid}.docx")
            c3.download_button("Download report (Markdown)", rep_md(bid), file_name=f"ActCheck_preliminary_report_{bid}.md")

    # Step 5: memo and letter
    with st.container(border=True):
        ui.step_header(5, "Memo & letter", "DBM format", "done" if d5 else ("now" if d3 else "lock"))
        if not d3:
            st.caption("🔒 Approve the review in Step 3 to unlock.")
            return
        ui.html('<div class="ac-step-d">Drafts in the DBM memorandum and letter layout (Tahoma), pre-filled from the approved review and your '
                'comments. Offices, dates and the addressee are bracketed for you to complete; the position is yours to decide.</div>')
        approved = rec.get("approved_review") or {}
        comments = rec.get("comments") or approved.get("preliminary_comments", [])
        mf = rec.get("memo_fields")
        bureau = st.text_area("Comments of the concerned bureaus to include (optional, e.g. BMB / OPCCB)", value="" if mf else "", key="bureau")
        c1, c2 = st.columns(2)
        if not mf or c1.button("Rebuild the memo from the approved review and comments"):
            mf = docs.memo_prefill(bid, approved, comments, bureau, row.get("status", ""))
            store.save(bid, "memo_fields", mf, "Memo pre-filled")
            store.set_status(bid, "memo drafted")
            st.rerun()
        if c2.button(f"Redraft the narrative with {AGENT3}", disabled=not live):
            from agents.appraisal import run_memo
            with st.spinner("Drafting..."):
                ai = run_memo(bid, dict(approved, preliminary_comments=comments), bureau)["memo"]
            store.save(bid, "memo_fields", docs.apply_ai(mf, ai), f"{AGENT3} memo draft")
            st.rerun()
        free_route(f"p3memo_{bid}", lambda: build_memo_messages(bid, dict(approved, preliminary_comments=comments), bureau),
                   lambda out: store.save(bid, "memo_fields", docs.apply_ai(mf, out), "Memo (free route)"))
        mt1, mt2 = st.tabs(["Memorandum for the Secretary", "Letter to the committee or principal author"])
        with mt1:
            ui.html("<p><b>Your position</b></p>")
            p1, p2 = st.columns([1.2, 2])
            cur = next((i for i, x in sorted(enumerate(docs.POSITIONS), key=lambda y: -len(y[1]))
                        if docs.position_decided(mf) and x.upper() in (mf.get("s4") or "")), None)
            pos = p1.radio("Position", docs.POSITIONS, horizontal=False, label_visibility="collapsed", index=cur, key=f"pos_{bid}")
            extra = p2.text_area("Reason or conditions (optional)", key="pos_extra", height=90)
            if st.button("Set position in the memo", disabled=pos is None):
                txt = (f"In view of the foregoing, we recommend that the DBM manifest its position to {pos.upper()} the bill"
                       + (", subject to the comments above" if "amend" in pos else "") + "." + (f" {extra.strip()}" if extra.strip() else ""))
                store.save(bid, "memo_fields", dict(mf, s4=txt), f"Reviewer set the position: {pos}")
                st.rerun()
            new = field_editor(f"memo_{bid}", mf, docs.MEMO_FIELDS)
            if new:
                store.save(bid, "memo_fields", new, "Reviewer edited the memo")
                st.rerun()
            for x in governance_flags(docs.memo_text(mf), "letter"):
                st.warning(x)
            paper(mf, "memo")
            st.download_button("Download memo (Word, Tahoma)", docs.memo_docx(mf), file_name=f"Memo_for_the_Secretary_{bid}.docx", type="primary")
        with mt2:
            if not docs.position_decided(mf):
                st.info("Set your position in the memorandum first; the letter conveys that position.")
            else:
                lf = rec.get("letter_fields")
                l1, l2 = st.columns(2)
                if not lf or l1.button("Rebuild the letter from the memo"):
                    lf = docs.letter_prefill(bid, mf)
                    store.save(bid, "letter_fields", lf, "Letter pre-filled")
                    store.set_status(bid, "letter drafted")
                    st.rerun()
                if l2.button(f"Redraft the paragraphs with {AGENT3}", disabled=not live):
                    from agents.appraisal import run_letter
                    with st.spinner("Drafting..."):
                        ai = run_letter(bid, docs.memo_text(mf))["letter"]
                    store.save(bid, "letter_fields", docs.apply_ai(lf, ai), f"{AGENT3} letter draft")
                    st.rerun()
                free_route(f"p3letter_{bid}", lambda: build_letter_messages(bid, docs.memo_text(mf)),
                           lambda out: store.save(bid, "letter_fields", docs.apply_ai(lf, out), "Letter (free route)"))
                new = field_editor(f"letter_{bid}", lf, docs.LETTER_FIELDS)
                if new:
                    store.save(bid, "letter_fields", new, "Reviewer edited the letter")
                    st.rerun()
                for x in governance_flags(docs.letter_text(lf), "letter"):
                    st.warning(x)
                paper(lf, "letter")
                st.download_button("Download letter (Word, Tahoma)", docs.letter_docx(lf), file_name=f"Letter_{bid}.docx", type="primary")
    with st.expander("Activity trail"):
        st.dataframe(pd.DataFrame(rec.get("trail", [])), use_container_width=True, hide_index=True)


# ---------------- BILLy ----------------
def _billy_ask(bid, question=None):
    """Callback: runs before the page redraws, so the answer is ready when the panel shows."""
    from agents import billy as B
    q = (question or st.session_state.get(f"billy_in_{bid}", "")).strip()
    if not q:
        return
    hist = st.session_state.setdefault(f"billy_{bid}", [])
    hist.append({"role": "user", "content": q})
    try:
        ans, _ = B.answer(bid, hist[:-1], q, bool(llm.api_key()))
    except Exception as e:
        ans = f"Sorry, I couldn't answer that: {e}"
    hist.append({"role": "assistant", "content": ans})
    st.session_state[f"billy_in_{bid}"] = ""


@st.fragment
def billy_body(bid):
    """Runs as a fragment: asking a question refreshes only this panel, so it stays open and answers quickly."""
    from agents import billy as B
    hist = st.session_state.setdefault(f"billy_{bid}", [])
    for m in hist[-6:]:
        if m["role"] == "user":
            ui.html(f'<div class="ac-msg u">{escape(m["content"])}</div>')
        else:
            st.markdown(m["content"])
    st.caption("Try one of these:" if not hist else "Ask another question:")
    for i, s in enumerate(B.suggestions(bid)[:4]):
        if not any(m["content"] == s for m in hist):
            st.button(s, key=f"bsug_{bid}_{i}", on_click=_billy_ask, args=(bid, s))
    st.text_input("Ask about this bill", key=f"billy_in_{bid}", placeholder="e.g. Who appoints the head of the new body?",
                  on_change=_billy_ask, args=(bid,))
    c1, c2 = st.columns(2)
    c1.button("Ask", key=f"billy_go_{bid}", on_click=_billy_ask, args=(bid,), type="primary")
    if hist:
        c2.button("Clear chat", key=f"billy_clr_{bid}", on_click=lambda: st.session_state.update({f"billy_{bid}": []}))
    st.caption("AI answers with checked citations." if bool(llm.api_key()) else "Search mode (no API key): I quote the bill's own sections.")


def billy():
    bid = st.session_state.get("bill") if st.session_state.get("bill") in bills else None
    with st.container(key="billy"):
        with st.popover("Ask Billy"):
            ui.html(f'<div class="ac-billy-head"><img src="{ui.STATIC}/billy.png" alt=""><div><b>BILLy</b>'
                    f'<span>Your review companion · {"reviewing " + escape(bills[bid]["label"]) if bid else "no bill open"}</span></div></div>')
            if not bid:
                st.write("Open a bill in the review workspace and I'll answer questions about it, citing its sections.")
                return
            billy_body(bid)


# ================= pages =================
if page == "Home":
    ws = watch_state()
    runs = ws.get("runs", [])
    inbox_p = ROOT / "data" / "watch" / "inbox.json"
    inbox = json.loads(inbox_p.read_text()) if inbox_p.exists() else []
    ui.hero(APP_NAME, SUBHEADING, TAGLINE, DESCRIPTION)
    last = runs[-1] if runs else {}
    c20 = cat[cat["congress"] == "20"]
    ui.stats([(f"{len(cat):,}", "Bills listed, 18th to 20th Congress", "House and Senate bills from public sources", ""),
              (f"{len(c20):,}", "Bills in the 20th Congress", f"{int((c20['chamber'] == 'House').sum()):,} House · {int((c20['chamber'] == 'Senate').sum()):,} Senate", "gold"),
              (f"{last.get('found', 0):,}", "New bills from the daily run",
               (f"Found on {last['time'][:10]} · {len(inbox):,} since the daily check began" if last else "The daily check runs at 06:17 Manila time"), "red")])

    ui.section("Bills by type", "What the bills propose",
               "Philippine bills can be classified by who or where they apply to and by what they propose to do. Shares are computed from each "
               "bill's title with ActCheck's rules (one primary type per bill), so read them as approximate.")
    which = st.radio("Congress", ["20th", "19th", "18th", "All"], horizontal=True, key="home_cong")
    d = cat if which == "All" else cat[cat["congress"] == which[:2]]
    n = max(len(d), 1)
    counts = d["type"].value_counts()
    rows = [(k, int(v), v / n) for k, v in counts.items()]
    ui.bars(rows, highlight="Government organization and mandates")
    ui.html("<p style='margin:1.1rem 0 .1rem'><b>Who the bills apply to</b></p>")
    app_counts = d["applies_to"].value_counts()
    ui.stack([(k, int(app_counts.get(k, 0)), app_counts.get(k, 0) / n) for k in typology.APPLICATION], ["#0B2545", "#D4A72C", "#B8322A"])
    ui.note("<b>Why scope matters for review.</b> Under Article VI, Section 24 of the 1987 Constitution, appropriation, revenue or tariff bills, "
            "bills authorizing an increase of the public debt, bills of local application and private bills originate exclusively in the House "
            "of Representatives; the Senate may propose or concur with amendments. ActCheck flags these bills so the reviewer can follow the "
            "House version. Highlighted in gold: the pilot type the agents are tested on (government organization and mandates).")

    ui.section("How a review flows", "From a newly filed bill to comments for legislators",
               "Three agents prepare the evidence; the analyst checks each step before the next one opens and decides the position.")
    ui.flow([("Every morning", "Daily check", "Reads the House documents server and the Senate bill listing for new filings, downloads their text "
              "and classifies each bill.", "Output: new bills on the Bills page", True),
             ("Step 1", f"{AGENT1} · Trace the bill", "Finds earlier versions, counterparts and refiled copies in both chambers, and the "
              "existing laws the bill touches.", "Output: legislative history with checked citations", False),
             ("Step 2", f"{AGENT2} · Spot the changes", "Compares the bill with the closest related measure, section by section, and flags "
              "what changed and its likely cost effect.", "Output: substantial differences and design options", False),
             ("Step 3", f"{AGENT3} · Weigh the impact", "Estimates a first-year cost range, notes risks and overlaps, and drafts preliminary "
              "comments; a red-teamer checks the draft.", "Output: preliminary review and comments", False),
             ("The analyst", "Decide and send", "Ticks each checklist, edits the comments, sets the position and finalizes the DBM memo and letter.",
              "Output: memo to the Secretary and letter to Congress", True)])

elif page == "Bills":
    ui.section("Legislative measures", "Every House and Senate bill",
               "Filter by Congress, bill type, type of measure and status. Click a title for details, or <b>Review</b> to send the bill to your "
               "review workspace. Bills without full text are fetched from their source when you review them.")
    with st.container(border=True):
        f1, f2, f3, f4 = st.columns([0.8, 0.9, 1.6, 1.5])
        congress = f1.selectbox("Congress", ["20th", "19th", "18th", "All"])
        btype = f2.selectbox("Bill type", ["All", "House Bill", "Senate Bill"])
        ttype = f3.selectbox("Type", ["All types"] + typology.CATEGORY_NAMES)
        statuses = ["All statuses"] + list(cat["status"].value_counts().index)
        status = f4.selectbox("Status", statuses)
        s1, s2, s3 = st.columns([2.6, 1.1, 0.9])
        q = s1.text_input("Search bill number, title or subject", placeholder="e.g. HB 2322, water resources, coast guard")
        applies = s2.selectbox("Applies to", ["All"] + typology.APPLICATION)
        fulltext = s3.toggle("Full text only", value=False)
    df = cat
    if congress != "All":
        df = df[df["congress"] == congress[:2]]
    if btype != "All":
        df = df[df["bill_type"] == btype]
    if ttype != "All types":
        df = df[df["type"] == ttype]
    if status != "All statuses":
        df = df[df["status"] == status]
    if applies != "All":
        df = df[df["applies_to"] == applies]
    if fulltext:
        df = df[df["reviewable"]]
    if q:
        key = q.lower().replace(" ", "")
        hay = (df["label"] + df["title"] + df["short_title"]).str.lower().str.replace(" ", "", regex=False)
        df = df[hay.str.contains(key, regex=False)]
    df = df.reset_index(drop=True)
    sig = (congress, btype, ttype, status, applies, fulltext, q)
    if st.session_state.get("bills_sig") != sig:
        st.session_state["bills_sig"], st.session_state["bills_page"] = sig, 1
    per = 20
    pages = max(1, -(-len(df) // per))
    pg = min(st.session_state.get("bills_page", 1), pages)
    st.caption(f"{len(df):,} bills match · page {pg} of {pages:,}")
    widths = [1.0, 5.4, 1.2, 1.9, 0.8, 1.0]
    ui.html('<div class="ac-thead" style="grid-template-columns:' + " ".join(f"{w}fr" for w in widths) +
            '"><span>Bill No.</span><span>Title</span><span>Bill type</span><span>Status</span><span>View bill</span><span>Review</span></div>')
    with st.container(key="billgrid"):
        for _, r in df.iloc[(pg - 1) * per: pg * per].iterrows():
            r = r.to_dict()
            c = st.columns(widths, vertical_alignment="center")
            c[0].markdown(f'<div class="ac-billno">{escape(r["label"])}</div>', unsafe_allow_html=True)
            title = (r["short_title"] or r["title"] or "(title not yet available)")
            title = title if len(title) <= 190 else title[:189].rsplit(" ", 1)[0] + "…"
            for ch in "*_[]`#<>":
                title = title.replace(ch, "\\" + ch)
            if c[1].button(title, key=f"t_{r['id']}", type="tertiary"):
                bill_dialog(r)
            c[1].markdown(f'<div class="ac-filed">Filed {escape(r["date_filed"] or "date not listed")}'
                          + (" · full text" if r["reviewable"] else "") + "</div>", unsafe_allow_html=True)
            c[2].markdown(r["bill_type"])
            c[3].markdown(f'<span class="ac-badge">{escape(r["status"])}</span>', unsafe_allow_html=True)
            if r["source_url"]:
                c[4].markdown(f'<div class="ac-view"><a href="{escape(r["source_url"])}" target="_blank">PDF ↗</a></div>', unsafe_allow_html=True)
            if c[5].button("Review", key=f"r_{r['id']}"):
                start_review(r)
    p1, p2, p3 = st.columns([1, 2, 1])
    if p1.button("← Previous", disabled=pg <= 1):
        st.session_state["bills_page"] = pg - 1
        st.rerun()
    p2.markdown(f"<div style='text-align:center;padding-top:.4rem'>Page {pg} of {pages:,}</div>", unsafe_allow_html=True)
    if p3.button("Next →", disabled=pg >= pages):
        st.session_state["bills_page"] = pg + 1
        st.rerun()

elif page == "Review workspace":
    queue = [(k, r) for k, r in store.queue_list() if k in bills]
    if st.session_state.get("bill") not in bills and queue:
        st.session_state["bill"] = queue[0][0]
    left, right = st.columns([1, 3.3])
    with left:
        ui.html('<div class="ac-kicker" style="margin-top:1.2rem">Bills under review</div>')
        if not queue:
            st.caption("No bills yet. Click Review on the Bills page.")
        for k, r in queue:
            active = k == st.session_state.get("bill")
            with st.container(border=True):
                st.markdown(f"**{bills[k]['label']}** · {bills[k]['congress']}th")
                st.caption(f"{bills[k]['title'][:80]}… · {r.get('status', 'new')}")
                if st.button("Open" if not active else "Open ✓", key=f"q_{k}", disabled=active, use_container_width=True):
                    st.session_state["bill"] = k
                    st.rerun()
    with right:
        bid = st.session_state.get("bill")
        if not bid or bid not in bills:
            ui.notice("No bill open. Go to <b>Bills</b> and click <b>Review</b> on any bill.", "navy")
        else:
            store.queue(bid)
            case(bid)

elif page == "Library":
    ui.section("Document library", "Full texts in ActCheck", "Bills, committee reports and existing laws, split into sections for citation.")
    lib = pd.DataFrame([{k: b.get(k) for k in ("id", "label", "congress", "family", "kind", "n_sections", "text_source", "title")}
                        for b in bills.values()])
    st.dataframe(lib, use_container_width=True, hide_index=True, height=320)
    pick_id = st.selectbox("Read a document", sorted(bills), format_func=lambda x: f"{x} · {bills[x]['title'][:100]}")
    for s in secs.get(pick_id, []):
        with st.expander(f"Sec. {s['no']}. {s['heading']}"):
            st.write(s["text"])

elif page == "Run log":
    ui.section("Run log", "Every agent run and daily check", "For the portfolio's run log and AI-use disclosure.")
    rows = []
    for f in sorted((ROOT / "logs").glob("*.jsonl")):
        for x in f.read_text().splitlines():
            try:
                d = json.loads(x)
            except ValueError:
                continue
            meta = d.get("meta") if isinstance(d.get("meta"), dict) else {}
            flat = {k: v for k, v in (d | meta).items()
                    if k not in ("output", "user_prompt", "reply", "prompt", "checks", "meta") and not isinstance(v, (dict, list))}
            if isinstance(d.get("checks"), list):
                flat["citations verified"] = f"{sum(1 for c in d['checks'] if c.get('check') == 'verified')}/{len(d['checks'])}"
            rows.append(flat | {"log": f.name})
    if rows:
        st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)
    else:
        st.caption("No agent runs logged yet in this deployment.")
    runs = watch_state().get("runs", [])
    if runs:
        ui.section("Daily check", "Runs of the daily check")
        st.dataframe(pd.DataFrame(runs[::-1]), use_container_width=True, hide_index=True)
    vl = ROOT / "docs" / "VERSION_LOG.md"
    if vl.exists():
        with st.expander("Version log"):
            st.markdown(vl.read_text())

else:
    import howitworks
    howitworks.render(AGENT1, AGENT2, AGENT3)

ui.footer(APP_NAME, LABEL)
billy()
