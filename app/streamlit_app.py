"""ActCheck: an agentic AI system for Philippine legislative review.

    streamlit run app/streamlit_app.py

Pages: Overview (summary data, bill typology, how a review flows) -> Bills (every bill; Type and Status
filters; click a title for details; Review sends it to the workspace) -> Review workspace (bills under
review; Step 1 TrAIce, Step 2 CompAIre, Step 3 ApprAIsal, each with a run button and a reviewer
checklist that unlocks the next step; comments and report; DBM-format memo and letter) -> Library ->
Run log -> How it Works. BILLy, the review companion, floats in the corner of every page.

Without an API key, every rules-only part works, BILLy answers in search mode, and each agent step has
a free route (download the prompt, run it in a Claude chat, paste the reply back to check and save it).
"""
import json
import re
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

from agents import llm, store, reports, documents as docs  # noqa: E402
from agents.names import APP_NAME, AGENT1, AGENT2, AGENT3  # noqa: E402
from pipeline import catalogue, typology, policy  # noqa: E402
from pipeline.compare import load, related_bills  # noqa: E402
import render  # noqa: E402
import ui  # noqa: E402
import fulltext  # noqa: E402
from icons import svg  # noqa: E402

SUBHEADING = "An Agentic AI System for Philippine Legislative Review"
TAGLINE = "Trace the bill. Spot the changes. Weigh the impact."
DESCRIPTION = ("A tool to aid government analysts to trace a bill's history, see what changed, and assess its legal and budget "
               "implications in order to provide comments for legislators.")
LABEL = "AI-assisted preliminary draft for DBM reviewer validation. Not an official position."
PILOT = "Creates a national agency (pilot)"
STATUS_COLOR = {"PENDING": "gold", "ENACTED": "green", "CONSOLIDATED/SUBSTITUTED": "navy", "NOT ENACTED": "red"}
APP_URL = "https://act-check.streamlit.app"      # the hosted portal (links that open in a new window)
ALL_PAGES = ["Overview", "Bills", "Review workspace", "How it Works", "Library", "Run log"]
PUBLIC_PAGES = [p for p in ALL_PAGES if p != "Review workspace"]
STEPS = ["Trace", "Compare", "Weigh", "Memo & letter"]
STEP_DESCS = ["Trace the bill", "Spot the changes", "Weigh the impact", "DBM format"]
WORKFLOW = [
    ("Every morning · 9:00 AM", "Daily check", "daily",
     ["Checks the House documents server for new bill numbers", "Catches up older House bills missing from the list",
      "Reads each bill, including scanned pages", "Sorts bills by type and flags LEDAC priority measures", "Reports any source that fails"],
     "New bills on the Bills page", True),
    ("Step 1 · Trace the bill", "TrAIce", "trace",
     ["Finds earlier versions in the 18th and 19th Congress", "Finds the counterpart in the other chamber and refiled copies",
      "Lists the existing laws the bill amends or overlaps", "Quotes a section for every link; each quote is checked"],
     "Legislative history with checked citations", False),
    ("Step 2 · Spot the changes", "CompAIre", "compare",
     ["Compares the bill with its closest related measure, section by section", "States the problem the bill addresses",
      "Lists substantial differences and their likely cost effect", "Shows design options seen in related bills"],
     "Substantial differences and design options", False),
    ("Step 3 · Weigh the impact", "ApprAIsal", "appraise",
     ["Estimates a first-year cost range (fixed calculator, 2026 budget data)", "Notes risks, overlaps and policy context",
      "Drafts preliminary comments and a checklist", "A second AI reviewer checks the draft", "Drafts the memo and letter in DBM format"],
     "Preliminary review, comments, memo and letter drafts", False),
    ("The analyst", "Decide and send", "analyst",
     ["Ticks each checklist to unlock the next step", "Edits the findings and comments", "Sets the DBM position",
      "Finalizes and signs off the memo and letter"],
     "DBM memo to the Secretary and letter to Congress", True),
]

st.set_page_config(page_title=f"{APP_NAME} · {SUBHEADING}", page_icon=str(ROOT / "app" / "static" / "favicon.png"),
                   layout="wide", initial_sidebar_state="collapsed")
ui.inject()
bills, secs = load()


@st.cache_resource(show_spinner="Loading the bill list...", max_entries=1)
def bill_table(stamp):
    df = pd.DataFrame(catalogue.build(stamp))
    # memory: repeated labels stored once (category columns); free text and searched columns stay as text
    for c in ("chamber", "congress", "status", "status_basis", "status_group", "status_sub", "bill_type", "committee",
              "scope", "text", "found", "source", "date_basis", "ledac", "date_filed"):
        if c in df:
            df[c] = df[c].astype("category")
    catalogue.build.cache_clear()          # the list of dicts is no longer needed once the table exists
    return df


# The rules-only analyses take a few seconds each; cache them per bill (the stamp changes when the corpus does).
@st.cache_data(show_spinner="Gathering the evidence...", max_entries=64)
def c_evidence(bid, stamp):
    from agents.research import evidence_pack
    return evidence_pack(bid)


@st.cache_data(show_spinner="Estimating the budgetary requirements...", max_entries=32)
def c_req(bid, stamp):
    from agents import budget, costing
    return budget.requirements(costing.cost_range(bid))


@st.cache_data(show_spinner="Drafting the ApprAIsal output...", max_entries=32)
def c_adraft(bid, stamp, t_out, c_out):
    from agents import appraise, costing
    return appraise.rule_draft(bid, t_out, c_out, costing.cost_range(bid))


@st.cache_data(show_spinner="Drafting the CompAIre output...", max_entries=32)
def c_cdraft(bid, stamp, t_out):
    """ActCheck's rule-based CompAIre draft (no AI)."""
    from agents import compaire
    return compaire.rule_draft(bid, t_out)


@st.cache_data(show_spinner="Drafting the TrAIce output...", max_entries=32)
def c_traice(bid, stamp):
    """ActCheck's rule-based TrAIce draft (no AI); shown until an AI run is saved."""
    from agents import traice
    row = row_of(bid) or {}
    b = bills[bid]
    return traice.rule_draft(bid, c_evidence(bid, stamp), row, policy.context({"title": b["title"], "congress": b["congress"]}), row.get("type", ""))


@st.cache_data(show_spinner="Finding related bills...", max_entries=64)
def c_related(bid, stamp):
    return related_bills(bid, top=15)


@st.cache_data(show_spinner="Comparing the bills...", max_entries=64)
def c_compare(bid, ref, stamp):
    from agents.diagnosis import report_markdown
    return report_markdown(bid, ref)


@st.cache_data(show_spinner="Comparing the bills...", max_entries=64)
def c_facts(bid, ref, stamp):
    from agents.diagnosis import fact_diff
    return fact_diff(bid, ref)


@st.cache_data(show_spinner="Matching sections...", max_entries=64)
def c_align(bid, ref, stamp):
    from pipeline.compare import align
    return align(bid, ref)


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


# Public view by default. Reviewer check-in shows the review workspace and the AI settings; for the course
# demonstration it needs only a click (no password).
if st.query_params.get("checkin") == "1":
    st.session_state["reviewer"] = True
    st.session_state["_goto"] = "Review workspace"
    del st.query_params["checkin"]
if st.query_params.get("reviewer") == "1":
    st.session_state["reviewer"] = True
REVIEWER = bool(st.session_state.get("reviewer"))
if REVIEWER:
    st.query_params["reviewer"] = "1"          # keeps the check-in when a link on the page reloads it
elif "reviewer" in st.query_params:
    del st.query_params["reviewer"]
PAGES = ALL_PAGES if REVIEWER else PUBLIC_PAGES
qp_page = st.query_params.get("page")
if qp_page == "Home":
    qp_page = "Overview"
# a link from the Review workspace: open the Library on Full Text of Bills with this document's text
qp_doc = st.query_params.get("doc")
if qp_doc:
    if qp_doc in bills:
        st.session_state["lib_view"], st.session_state["open_doc"] = "bills", qp_doc
        qp_page = "Library"
    del st.query_params["doc"]
if qp_page in PAGES:
    st.session_state["_goto"] = qp_page
    del st.query_params["page"]
if "_goto" in st.session_state:
    st.session_state["nav"] = st.session_state.pop("_goto")
if st.session_state.get("nav") not in PAGES:
    st.session_state["nav"] = "Overview"


def check_in():
    st.session_state["reviewer"] = True
    st.session_state["_goto"] = "Review workspace"


def check_out():
    st.session_state["reviewer"] = False
    st.session_state["_goto"] = "Overview"
    if "reviewer" in st.query_params:
        del st.query_params["reviewer"]

@st.dialog("Welcome to ActCheck!", width="medium")
def welcome_dialog():
    """First visit: the visitor picks the view (public, or analyst with the Review workspace)."""
    ui.html(f'<div class="ac-welcome"><img src="{ui.STATIC}/billy.png" alt="BILLy, ActCheck\'s guide">'
            '<p>Hi, I\'m <b>BILLy</b>, your guide to ActCheck, an agentic AI system for Philippine legislative review.</p>'
            '<p class="q">Are you a <b>Public Visitor</b> or an <b>Analyst</b>?</p></div>')
    w1, w2 = st.columns(2)
    with w1:
        pub = st.button("Public Visitor", key="w_public", use_container_width=True)
        st.caption("Civil society. Public view, with access to civil society reporting only.")
    with w2:
        ana = st.button("Analyst", key="w_analyst", type="primary", use_container_width=True)
        st.caption("Reviewer. Government agency view, with access to the Review workspace.")
    if pub or ana:
        st.session_state["reviewer"] = bool(ana)
        st.session_state["_goto"] = "Review workspace" if ana else "Overview"
        if ana:
            st.query_params["reviewer"] = "1"
        else:
            st.query_params["visitor"] = "1"
            if "reviewer" in st.query_params:
                del st.query_params["reviewer"]
        st.rerun()


if not st.session_state.get("_welcomed") and "reviewer" not in st.query_params and "visitor" not in st.query_params:
    st.session_state["_welcomed"] = True
    welcome_dialog()

# When the page changes, hide what is left of the previous page while the new one loads (Streamlit otherwise
# keeps it on screen, faded). Only on that run: within a page, content stays visible during refreshes.
_switched = st.session_state.get("_last_page") != st.session_state["nav"]
st.session_state["_last_page"] = st.session_state["nav"]
ui.html("<style>[data-stale='true']{display:none !important;}</style>" if _switched else "<span></span>")

live = bool(llm.api_key())
if REVIEWER:
  with st.sidebar:
    st.markdown("### Reviewer settings")
    pasted = st.text_input("AI access key from Anthropic (optional; kept only while this page is open)", type="password")
    if pasted:
        st.session_state["user_api_key"] = pasted
    st.selectbox("Model", list(llm.MODELS), format_func=lambda m: llm.MODELS[m], key="model",
                 help="Haiku is about 20 times cheaper; Sonnet gives better citations and comparisons.")
    live = bool(llm.api_key())
    st.write("AI agents:", "**on**" if live else "**off**. ActCheck still shows its own analysis, BILLy searches the bill's text, and each agent can be run in your Claude chat.")
    st.caption(LABEL)

with st.container(key="topbar"):
    ui.masthead(APP_NAME, SUBHEADING, REVIEWER)
    with st.container(key="navrow"):
        n1, n2 = st.columns([5, 1.25], vertical_alignment="center")
        with n1:
            page = st.radio("Navigation", PAGES, key="nav", horizontal=True, label_visibility="collapsed")
        with n2:
            if REVIEWER:
                st.button("✓ Reviewer · Log Out", key="btn_checkout", on_click=check_out, use_container_width=True,
                          help="Return to the public view")
            else:
                st.button("Reviewer Log In", key="btn_checkin", on_click=check_in, type="primary", use_container_width=True,
                          help="Open the review workspace (no password needed for this course prototype)")
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
    with st.expander("No AI key? Run this step in your Claude chat instead"):
        st.caption("1) Download the instructions. 2) Open a new Claude chat, attach the file and ask Claude to follow it exactly. "
                   "3) Paste Claude's reply below. ActCheck checks the reply before saving it.")
        try:
            system, user = prompt_fn()
            st.download_button("Download the instructions", f"=== SYSTEM PROMPT ===\n{system}\n=== USER MESSAGE ===\n{user}",
                               file_name=f"prompt_{key}.txt", key=f"dl_{key}")
        except Exception as e:
            st.info(str(e))
            return
        reply = st.text_area("Paste Claude's reply", key=f"reply_{key}", height=140)
        if st.button("Check and save the reply", key=f"save_{key}", disabled=not reply.strip()):
            try:
                on_reply(llm.parse_json(reply) if json_reply else reply)
                st.success("Checked and saved.")
                st.rerun()
            except Exception as e:
                st.error(f"ActCheck could not read the reply ({e}). Make sure you pasted the whole reply.")


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
    from agents import traice
    new = not store.exists(row["id"]) or store.load(row["id"]).get("removed")
    store.queue(row["id"])
    if new and not traice.saved_ai(row["id"]):
        reports.queue_for_claude(row["id"], row["label"], row.get("title", ""))
    go("Review workspace", row["id"])


@st.dialog("Share a report on this bill", width="large")
def report_dialog(row):
    """Public input from civil society and others; contact details optional and seen only by reviewers."""
    if st.session_state.get("reports_sent", 0) >= 5:
        st.info("Thank you. You have sent several reports in this visit; please try again later.")
        return
    c1, c2 = st.columns([1, 3])
    c1.text_input("Bill number", value=f'{row["label"]} ({row["congress"]}th Congress)', disabled=True)
    c2.text_input("Title", value=row["title"] or row["short_title"], disabled=True)
    st.markdown("**What is your report about?** Choose the part of the review it concerns, then the topic.")
    grp = st.radio("Part of the review", list(reports.GROUPS), horizontal=True, key="rep_group",
                   format_func=lambda g: g if g == reports.OTHERS else f"{g} (Step {reports.STEP[g]})")
    st.caption(f"{grp}: {reports.GROUP_HELP[grp]}.")
    topic = st.selectbox("Topic", reports.GROUPS[grp], key=f"rep_topic_{grp}")
    cat_ = reports.category(grp, topic)
    msg = st.text_area("Your message", height=140, placeholder="What should the reviewers know? Please be specific and cite sources where you can.")
    up = st.file_uploader(f"Attach files (optional; up to {reports.MAX_FILE_MB} MB each)", type=reports.FILE_TYPES, accept_multiple_files=True)
    st.markdown("**Your details (optional)**")
    d1, d2, d3 = st.columns(3)
    nm = d1.text_input("Name")
    em = d2.text_input("Email")
    ph = d3.text_input("Contact number")
    gives = any(x.strip() for x in (nm, em, ph))
    ok = st.checkbox("I agree that ActCheck may keep this report and any contact details I gave, to review it and follow up if needed "
                     "(Data Privacy Act of 2012). Contact details are seen only by reviewers, never published.", value=False)
    too_big = [f.name for f in up or [] if len(f.getvalue()) > reports.MAX_FILE_MB * 1024 * 1024]
    problems = []
    if len(msg.strip()) < 15:
        problems.append("Please write a message of at least a sentence.")
    if not reports.valid_email(em.strip()):
        problems.append("Please check the email address.")
    if too_big:
        problems.append("Too large: " + ", ".join(too_big))
    if gives and not ok:
        problems.append("Please tick the consent box to send your contact details, or leave them blank.")
    if st.button("Send report", type="primary", disabled=bool(problems) or (not ok and gives)):
        reports.save(row["id"], row["label"], row["title"] or row["short_title"], cat_, msg, nm, em, ph, up)
        st.session_state["reports_sent"] = st.session_state.get("reports_sent", 0) + 1
        st.success("Thank you. Your report was sent to the reviewers.")
    elif problems and (msg or gives or up):
        st.caption(" ".join(problems))
    st.caption("This is a student prototype, not an official channel of the House, the Senate or the DBM.")


def report_body(x, key):
    """One public report, as a reviewer sees it: category, date, sender, message, contact details and files."""
    who = x.get("name") or "Sender did not give a name"
    st.markdown(f"**{escape(x.get('category', ''))}**")
    st.caption(f"Received {str(x.get('time', ''))[:16].replace('T', ' ')} UTC · {escape(who)}"
               + (" · kept in the Google Sheet" if x.get("_store") == "sheet" else " · kept on this server"))
    st.write(x.get("message", ""))
    if x.get("email") or x.get("phone"):
        st.caption("Contact (reviewers only): " + " · ".join(v for v in (x.get("email"), x.get("phone")) if v))
    for j, (name, where) in enumerate(reports.file_links(x)):
        if where.startswith("http"):
            st.link_button(f"📎 {name} (opens in Google Drive)", where)
        elif Path(where).exists():
            st.download_button(f"📎 {name}", Path(where).read_bytes(), file_name=name, key=f"rf_{key}_{j}")
    st.divider()


@st.dialog("Public reports", width="large")
def reports_dialog(items, where):
    st.markdown(f"#### {escape(where)}")
    st.caption("Shared from the Bills page by civil society organizations and other members of the public. Treat each report as a lead "
               "to check against the bill and the sources, not as evidence on its own.")
    for i, x in enumerate(items):
        report_body(x, f"dlg{i}")


def report_notice(bid, step, where):
    """Clickable notice in the part of the Review workspace that a public report concerns."""
    items = [x for x in reports.all_reports(bid) if reports.step_of(x.get("category")) == step]
    if not items:
        return
    n = len(items)
    cats = sorted({(x.get("category", "").split(":", 1)[1] if x.get("category", "").split(":")[0] in reports.STEP
                    else x.get("category", "").split(":")[0]).strip() for x in items})
    with st.container(key=f"repnote_{step}"):
        if st.button(f"📣 {n} public report{'s' if n > 1 else ''} from a CSO or member of the public concern{'s' if n == 1 else ''} "
                     f"{where}: {'; '.join(cats)}. Click to read.", key=f"repnote_btn_{step}"):
            reports_dialog(items, f"{where}: {n} public report{'s' if n > 1 else ''} on {bills[bid]['label']}")


DOC_TYPE = {"law": "Law", "substitute": "Substitute bill", "committee_report": "Committee report", "reference": "Reference", "other": "Other"}


def doc_type(b):
    if b.get("kind") == "bill":
        return {"HB": "House Bill", "SB": "Senate Bill"}.get(b.get("chamber"), "Bill")
    return DOC_TYPE.get(b.get("kind"), str(b.get("kind", "")).replace("_", " ").capitalize())


def doc_group(b):
    f = b.get("family") or ""
    return "New bills (daily check)" if f == "New measures (watcher)" else f


@st.dialog("Full text", width="large")
def doc_dialog(bid):
    b = bills[bid]
    st.markdown(f"### {escape(str(b.get('label', '')))}" + (f" · {b['congress']}th Congress" if b.get("congress") else ""))
    ui.html(f'<div class="ac-billtitle">{escape(b.get("title") or "")}</div>')
    st.caption(f"{doc_type(b)} · {b.get('n_sections') or 0} sections · "
               + ("text kept by ActCheck from the official document" if b.get("kind") == "reference" else
                  "text recognized from a scanned PDF; check quotes against the original" if b.get("text_source") == "ocr" else "text read from the PDF")
               + f" · group: {doc_group(b)}")
    ss = secs.get(bid, [])
    for i, s_ in enumerate(ss):
        with st.expander(f"Sec. {s_['no']}. {s_['heading']}"):
            nxt = ss[i + 1]["text"] if i + 1 < len(ss) else ""
            ui.html(fulltext.html(fulltext.section_paragraphs(b.get("file", ""), s_["text"], nxt)))


@st.dialog("Bill details", width="large")
def bill_dialog(row):
    st.markdown(f"### {escape(row['label'])} · {row['congress']}th Congress")
    ui.badges([(row["bill_type"], "navy"), (row["type"], "gold"), (row["applies_to"], ""), (row["status"], ""),
               ("Full text in ActCheck" if row["reviewable"] else "Listing only", "green" if row["reviewable"] else ""),
               (house_note(row), "red"), (("LEDAC priority: " + row["ledac"]) if row.get("ledac") else "", "red")])
    ui.html(f'<div class="ac-billtitle">{escape(row["title"] or row["short_title"] or "(title not yet available)")}</div>')
    meta = [("Short title", row["short_title"]), ("Filed", (row["date_filed"] + (f" (source: {row['date_basis']})" if row.get("date_basis") else ""))
                                                       if row["date_filed"] else "date not clearly visible; verify in file"), ("Status", f'{row.get("status_group", "")} · {row.get("status_sub", "")} ({row["status"]})'),
            ("Where the status comes from", row.get("status_basis", "")), ("Committee", row["committee"]),
            ("Author", row["author"]), ("Listed from", row["source"])]
    st.caption(" · ".join(f"{k}: {v}" for k, v in meta if v))
    st.caption("The type and scope are assigned from the bill's title and should be confirmed during review.")
    if REVIEWER:
        rep = reports.all_reports(row["id"])
        if rep:
            with st.expander(f"Public reports on this bill ({len(rep)})"):
                for i, x in enumerate(rep):
                    report_body(x, f"bd{i}")
    c1, c2 = st.columns(2)
    if REVIEWER:
        if c1.button("Review this bill", type="primary", key=f"dlg_rev_{row['id']}"):
            start_review(row)
    else:
        c1.caption("Reviewers can send this bill to the review workspace after logging in (button at the top right).")
    if row["source_url"]:
        c2.link_button("View bill (source document)", row["source_url"])


# ---------------- Review workspace helpers ----------------
def checklist(bid, step, items, heading="Reviewer checklist: tick every item to unlock the next step", subs=None, notes=None):
    """Short checklist with one notes-and-attachments box at the end. Returns True when every item is ticked.
    `subs` maps an item's index to short points shown under it."""
    rec = store.load(bid)
    allcl = rec.get("checklist") or {}
    cl = dict(allcl.get(step) or {})
    with st.container(key=f"chk_{step}"):
        if heading:
            ui.html(f'<div class="ac-check"><div class="ac-check-h">✓ {escape(heading)}</div></div>')
        else:
            st.caption("Tick every item to unlock the next step.")
        changed = False
        for i, item in enumerate(items):
            cur = cl.get(str(i)) or {}
            done = st.checkbox(item, value=bool(cur.get("done")), key=f"ck_{bid}_{step}_{i}")
            pts = (subs or {}).get(i) or []
            if pts:
                ui.html('<ul class="ac-subchk">' + "".join(f"<li>{escape(p)}</li>" for p in pts) + "</ul>")
            if (notes or {}).get(i):
                ui.html(notes[i])
            if done != bool(cur.get("done")):
                cl[str(i)] = dict(cur, done=done)
                changed = True
        box = dict(cl.get("_notes") or {"note": "", "files": []})
        with st.expander("Notes and attachments (if needed)" + (f" · {len(box.get('files', []))} file(s)" if box.get("files") else "")
                         + (" · note added" if box.get("note") else "")):
            note = st.text_area("Notes", value=box.get("note", ""), key=f"nt_{bid}_{step}", height=90,
                                label_visibility="collapsed", placeholder="Findings, corrections or anything to follow up for this step")
            up = st.file_uploader("Attach a file", key=f"up_{bid}_{step}", label_visibility="collapsed")
            files = list(box.get("files", []))
            if up is not None and not any(f.endswith(up.name.replace(" ", "_")) for f in files):
                files.append(store.save_upload(bid, step, up.name, up.getvalue()))
            for f in files:
                st.caption(f"📎 {f}")
        if {"note": note, "files": files} != {"note": box.get("note", ""), "files": box.get("files", [])}:
            cl["_notes"] = {"note": note, "files": files}
            changed = True
        if changed:
            allcl[step] = cl
            store.save(bid, "checklist", allcl, trail=False)
            st.rerun()                       # refresh so the step locks and the progress bar reflect the change
        n_done = sum(1 for i in range(len(items)) if (cl.get(str(i)) or {}).get("done"))
        st.caption(f"{n_done} of {len(items)} items done.")
    return n_done == len(items) and len(items) > 0


from agents.traice import CHECKLIST as CHECK1  # noqa: E402
CHECK3 = ["The ApprAIsal output above is correct and its details are verified against official sources and records and will be added to the memo."]
CHECK2 = ["The CompAIre output above is correct and its details are verified against official sources and records and will be added to the memo."]


def pick_reference(bid, research_out):
    from agents import traice
    order = (traice.LABELS[2], traice.LABELS[3], traice.LABELS[1], traice.LABELS[0], traice.LABELS[4])
    sv = (traice.saved_ai(bid) or {}).get("output")
    out = sv if sv and (not research_out or "proposal" not in research_out) else research_out
    if out:
        for lab in order:
            for r in out.get("related", []):
                rl = traice.OLD.get(str(r.get("relationship", "")).lower().strip(), r.get("relationship"))
                rl = traice.LABELS[3] if rl in ("Senate version", "House version") else rl
                if rl == lab and r.get("id") in bills and r["id"] != bid:
                    return r["id"]
    rel = c_related(bid, catalogue.stamp())
    return rel[0]["id"] if rel else None


def paper(fields, kind):
    """On-screen preview of the memo or letter in the DBM layout (Tahoma)."""
    e = lambda s: escape(str(s or "")).replace("\n", "<br>")  # noqa: E731
    serif = "font-family:'Bookman Old Style',Georgia,serif;text-align:center"
    head = (f'<div style="text-align:center;font-size:.65rem;color:#888;font-style:italic">{docs.SEAL_NOTE}</div>'
            f'<div style="{serif};font-size:.8rem;letter-spacing:.04em">{docs.LETTERHEAD[0]}</div>'
            f'<div style="{serif};font-weight:700;font-size:1.02rem">{docs.LETTERHEAD[1]}</div>'
            + (f'<div style="{serif};font-size:.62rem;letter-spacing:.04em">{docs.LETTERHEAD[2]}</div>' if kind != "memo" else "")
            + '<div style="margin-bottom:.8rem"></div>')
    if kind == "memo":
        rows = "".join(f'<tr><td style="width:70px;vertical-align:top">{lab}</td><td style="width:14px;vertical-align:top">:</td>'
                       f'<td style="{"font-weight:700;" if k == "subject" else ""}text-align:justify">{e(fields.get(k))}</td></tr>'
                       for k, lab in (("thru", "Thru"), ("from_", "From"), ("subject", "Subject")))
        body = "".join((f'<p style="margin:.6rem 0 .2rem"><b>{lab}</b></p>' if k not in ("s8", "s9") else "")
                       + f'<div class="ac-memo" style="border:0;padding:0;margin:0 0 0 .4rem;font-size:.86rem">{render.memo_body_html(fields.get(k))}</div>'
                       for k, lab in docs.MEMO_FIELDS[5:] if str(fields.get(k) or "").strip())
        inner = (f'<p>{e(fields.get("date"))}</p><p><b>MEMORANDUM FOR {e(fields.get("memo_for"))}</b></p><table style="font-size:.86rem">{rows}</table>'
                 f'<hr style="border:0;border-top:1.5px solid #000">{body}')
    else:
        inner = (f'<p>{e(fields.get("date"))}</p><p><b>{e(fields.get("addressee"))}</b><br>{e(fields.get("office"))}<br>{e(fields.get("address"))}</p>'
                 f'<p>{e(fields.get("salutation"))}</p>'
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


def step_head(bid, n, title, sub, state):
    """Header of a step tile. A finished agent step folds up to its header; the reviewer opens it with Show."""
    key = f"open_{bid}_{n}"
    folded = state == "done" and n <= 3 and not st.session_state.get(key, False)
    with st.container(key=f"stephead{n}"):
        if state == "done" and n <= 3:
            h1, h2 = st.columns([6, 1.1], vertical_alignment="center")
            with h1:
                ui.step_header(n, title, sub, state)
            with h2:
                st.button("Show ▾" if folded else "Fold ▴", key=f"fold_{bid}_{n}", use_container_width=True,
                          on_click=lambda k=key, f=folded: st.session_state.__setitem__(k, f),
                          help="Open the finished step" if folded else "Fold the finished step to reduce scrolling")
            if folded:
                ui.html('<div class="ac-fold-note">Checklist complete. Click <b>Show</b> to open this step again.</div>')
        else:
            ui.step_header(n, title, sub, state)
    if folded:
        ui.html(f"<style>.st-key-step{n} > div:not(:has(.st-key-stephead{n})){{display:none !important;}}</style>")


def case(bid):
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
               (house_note(row), "red"), (("LEDAC priority: " + row["ledac"]) if row.get("ledac") else "", "red")])
    ui.html(f'<div class="ac-billtitle">{escape(b["title"])}</div>')
    src = row.get("source_url") or b.get("source_url") or ""
    has_text = bool(secs.get(bid, []))
    if src or has_text:
        o1, o2, _ = st.columns([1, 1.25, 4.5])
        if src:
            o1.link_button("📄 PDF", src, help="Open the source document in a new window", use_container_width=True)
        if has_text:
            o2.link_button("📖 Full Text", f"{APP_URL}/?page=Library&doc={bid}",
                           help="Open the text ActCheck has, section by section, in the Library (new window)", use_container_width=True)
    research_out = (rec.get("research") or {}).get("output")
    rev = (rec.get("review") or {}).get("output")

    def all_done(step, n):
        c = cl.get(step) or {}
        return n > 0 and all((c.get(str(i)) or {}).get("done") for i in range(n))
    mf_saved = rec.get("memo_fields") or {}
    d1, d2, d3 = all_done("t1", len(CHECK1)), all_done("c2", len(CHECK2)), all_done("a3", len(CHECK3))
    d4 = docs.position_decided(mf_saved) and bool(rec.get("letter_fields"))
    states = []
    for i, d in enumerate([d1, d2, d3, d4]):
        prev = [True, d1, d2, d3][i]
        states.append("done" if d else ("now" if prev else ""))
    st.session_state["_rail"] = (b["label"], states)
    report_notice(bid, 0, "this bill as a whole (corrections and other inputs)")
    if row.get("type") != "Government organization and mandates":
        ui.notice(f"<b>Outside the pilot scope.</b> This bill does not appear to create a new government agency. {AGENT1} and {AGENT2} can review "
                  f"any bill; {AGENT3}'s cost estimate is primarily designed for new agencies, so it may not be as precise.", "navy")

    # Step 1: TrAIce
    with st.container(border=True, key="step1"):
        from agents import traice
        step_head(bid, 1, AGENT1, "Trace the bill", "done" if d1 else "now")
        report_notice(bid, 1, f"Step 1 ({AGENT1}: legislative history)")
        ui.html('<div class="ac-step-d">Identifies what the bill proposes and why it matters for the budget, traces its legislative history, '
                'groups the related bills and laws by how they relate, and lists its fiscal requirements. Its output becomes Parts II and III '
                'of the memo, and its findings feed CompAIre and ApprAIsal.</div>')
        if live and st.button(f"▶ Run {AGENT1}", type="primary", key="run1"):
            from agents.research import run_agent as run1
            with st.spinner(f"{AGENT1} is tracing the bill..."):
                r1 = run1(bid, row, row.get("type", ""))
            store.save(bid, "research", {"output": r1["output"], "checks": r1["checks"]}, f"{AGENT1} run")
            store.set_status(bid, "in review")
            st.rerun()
        draft = c_traice(bid, catalogue.stamp())
        saved = traice.saved_ai(bid)
        use_saved = bool(saved) and (not research_out or ("proposal" in (saved.get("output") or {}) and "proposal" not in research_out))
        ai_out = (saved or {}).get("output") if use_saved else research_out
        ai_checks = (saved or {}).get("checks") if use_saved else (rec.get("research") or {}).get("checks")
        t_out = traice.normalize(ai_out, bid, draft)
        render.trace(bid, t_out, ai_checks if ai_out else None)

        # TrAIce output (memo Parts II and III, editable) and the reviewer checklist
        ui.html('<div class="ac-check"><div class="ac-check-h sc">✓ <span class="tr">TrAIce</span> output and reviewer checklist</div></div>')
        tm_default = {"salient": t_out.get("salient_features", ""), "related": t_out.get("related_measures_policy", "")}
        tm = rec.get("traice_memo") or tm_default
        ui.html('<div class="ac-memo"><h6>II. Salient Features</h6>' + render.memo_html(tm["salient"])
                + '<h6>III. Related Measures and Policy Considerations</h6>' + render.memo_html(tm["related"]) + '</div>')
        with st.expander("✏️ Edit this text (if needed)" + (" · edited by the reviewer" if rec.get("traice_memo") else "")):
            new = field_editor(f"tm_{bid}", tm, [("salient", "II. Salient Features"), ("related", "III. Related Measures and Policy Considerations")])
            if new is not None:
                store.save(bid, "traice_memo", new, "Reviewer edited the TrAIce output")
                st.rerun()
            if rec.get("traice_memo") and st.button("Reset to the TrAIce draft", key=f"tm_reset_{bid}"):
                store.save(bid, "traice_memo", None, "Reviewer reset the TrAIce output")
                st.rerun()
        from agents import grading
        gr = traice.grade(bid, t_out, ai_checks if ai_out else None)
        note = grading.note_html(gr, AGENT1)
        checklist(bid, "t1", CHECK1, heading=None, subs={0: t_out.get("reviewer_checks") or []}, notes={1: note})

    # Step 2: CompAIre
    from agents import compaire
    c_draft = c_cdraft(bid, catalogue.stamp(), t_out)
    c_saved = compaire.saved_ai(bid)
    c_ai = (rec.get("compaire") or {}).get("output") or (c_saved or {}).get("output")
    c_checks = (rec.get("compaire") or {}).get("checks") if rec.get("compaire") else (c_saved or {}).get("checks")
    c_out = compaire.normalize(c_ai, bid, c_draft)
    with st.container(border=True, key="step2"):
        step_head(bid, 2, AGENT2, "Spot the changes", "done" if d2 else ("now" if d1 else "lock"))
        report_notice(bid, 2, f"Step 2 ({AGENT2}: changes and design)")
        ui.html('<div class="ac-step-d">Building on TrAIce\'s salient features, compares the bill\'s major provisions, section by section, with the '
                'related measures that offer a real alternative, and recommends for each one whether to retain it, adapt an alternative '
                '(with or without revisions) or remove it, for example where it duplicates existing functions. Its output becomes Part IV '
                '(Comments and Recommendations) of the memo; possible duplications and cost effects go to ApprAIsal.</div>')
        if not d1:
            st.caption("🔒 Complete Step 1's checklist to unlock this step.")
        else:
            if live and st.button(f"▶ Run {AGENT2}", type="primary", key="run2"):
                with st.spinner(f"{AGENT2} is comparing the provisions..."):
                    r2 = compaire.run_agent(bid, t_out)
                store.save(bid, "compaire", {"output": r2["output"], "checks": r2["checks"]}, f"{AGENT2} run")
                st.rerun()
            render.compaire(bid, c_out, c_checks if c_ai else None)
            ui.html('<div class="ac-check"><div class="ac-check-h sc">✓ <span class="tr">CompAIre</span> output and reviewer checklist</div></div>')
            cm = rec.get("compaire_memo") or compaire.memo_text(c_out)
            ui.html('<div class="ac-memo"><h6>IV. Comments and Recommendations</h6>'
                    + (render.memo3_html(cm) if cm.strip() else "<p>No provision needs a decision: all major provisions are recommended for retention.</p>")
                    + "</div>")
            with st.expander("✏️ Edit this text (if needed)" + (" · edited by the reviewer" if rec.get("compaire_memo") else "")):
                new = field_editor(f"cm_{bid}", {"text": cm}, [("text", "IV. Comments and Recommendations")])
                if new is not None:
                    store.save(bid, "compaire_memo", new["text"], "Reviewer edited the CompAIre output")
                    st.rerun()
                if rec.get("compaire_memo") and st.button("Reset to the CompAIre draft", key=f"cm_reset_{bid}"):
                    store.save(bid, "compaire_memo", None, "Reviewer reset the CompAIre output")
                    st.rerun()
            from agents import grading
            gr2 = compaire.grade(bid, c_out, c_checks if c_ai else None)
            checklist(bid, "c2", CHECK2, heading=None, subs={0: c_out.get("reviewer_checks") or []},
                      notes={0: grading.note_html(gr2, AGENT2)})

    # Step 3: ApprAIsal
    from agents import appraise
    cost = c_cost(bid, catalogue.stamp())
    a_draft = c_adraft(bid, catalogue.stamp(), t_out, c_out)
    a_saved = appraise.saved_ai(bid)
    a_ai = (rec.get("apprAIsal") or {}).get("output") or (a_saved or {}).get("output")
    a_checks = (rec.get("apprAIsal") or {}).get("checks") if rec.get("apprAIsal") else (a_saved or {}).get("checks")
    a_out = appraise.normalize(a_ai, bid, a_draft)
    with st.container(border=True, key="step3"):
        step_head(bid, 3, AGENT3, "Weigh the impact", "done" if d3 else ("now" if d2 else "lock"))
        report_notice(bid, 3, f"Step 3 ({AGENT3}: cost, overlap or duplication, implementation or governance risk)")
        ui.html('<div class="ac-step-d">Estimates the budgetary requirements (Personnel Services, MOOE and Capital Outlay) and recommends how '
                'they fit the budget and the GAA; assesses possible duplication with existing agencies under the Government Optimization '
                'Act (RA No. 12231); proposes the overall recommendation; lists the DBM bureaus to consult; and compiles memo Parts V to VII.</div>')
        if not d2:
            st.caption("🔒 Complete Step 2's checklist to unlock this step.")
        else:
            if live and st.button(f"▶ Run {AGENT3}", type="primary", key="run3"):
                from agents import llm as _llm
                with st.spinner(f"{AGENT3} is weighing the impact..."):
                    system, user, _d = appraise.build_messages(bid, t_out, c_out, cost)
                    text, _meta = _llm.call("apprAIsal", system, user, max_tokens=8000)
                    o3 = json.loads(text[text.find("{"): text.rfind("}") + 1])
                store.save(bid, "apprAIsal", {"output": o3, "checks": appraise.check_output(o3, _d)}, f"{AGENT3} run")
                st.rerun()
            src = a_out.get("source", "ai")
            ui.badges([("Draft prepared by ActCheck's rules (no AI)", "gold")] if src == "rules" else [("Prepared by ApprAIsal (Claude)", "navy")])
            render.apprAIsal_fiscal(a_out, cost, c_req(bid, catalogue.stamp()), peso)
            render.apprAIsal_dup(a_out)
            render.referrals_table(a_out)
            # bureau comments, without a separate log-in: the reviewer sends the request by the usual channel and pastes the reply
            refs = a_out.get("referrals") or []
            if refs:
                binp = dict(rec.get("bureau_inputs") or {})
                with st.expander("Bureau comments (if needed): request to send, and the reply received" + (f" · {sum(1 for v in binp.values() if v)} received" if binp else "")):
                    st.caption("Copy each request into the usual referral memo or e-mail. When a bureau replies, paste its comment here; it goes "
                               "into Part IV of the memo under 'Comments of the concerned bureaus'.")
                    changed = False
                    for r in refs:
                        code = r.get("bureau", "")
                        st.markdown(f"**{code}** · {r.get('name', '')}" + (f" · send to {r['email']}" if r.get("email") else ""))
                        st.code(f"May we request the comments of the {r.get('name', code)} on {traice._doc(bid)}, particularly on: "
                                f"{r.get('why', '').rstrip('.')} ({r.get('parts', '')} of the attached preliminary review).", language=None)
                        v = st.text_area(f"Comment received from {code}", value=binp.get(code, ""), key=f"bi_{bid}_{code}", height=80)
                        if v != binp.get(code, ""):
                            binp[code], changed = v, True
                    if changed:
                        store.save(bid, "bureau_inputs", binp, "Bureau comments recorded")
                        st.rerun()
            ui.html('<div class="ac-check"><div class="ac-check-h sc">✓ <span class="tr">ApprAIsal</span> output and reviewer checklist</div></div>')
            am = rec.get("apprAIsal_memo") or appraise.memo_text(a_out)
            ui.html('<div class="ac-memo">' + "".join(
                f"<h6>{escape(blk.split(chr(10), 1)[0])}</h6>" + render.memo_body_html(blk.split(chr(10), 1)[1] if chr(10) in blk else "")
                for blk in am.split("\n\n") if blk.strip()) + "</div>")
            st.caption(f"Part VII is {AGENT3}'s proposed recommendation ({a_out['recommendation']['label']}); you confirm it in Step 4.")
            with st.expander("✏️ Edit this text (if needed)" + (" · edited by the reviewer" if rec.get("apprAIsal_memo") else "")):
                new = field_editor(f"am_{bid}", {"text": am}, [("text", "Parts V to VII")])
                if new is not None:
                    store.save(bid, "apprAIsal_memo", new["text"], "Reviewer edited the ApprAIsal output")
                    st.rerun()
                if rec.get("apprAIsal_memo") and st.button("Reset to the ApprAIsal draft", key=f"am_reset_{bid}"):
                    store.save(bid, "apprAIsal_memo", None, "Reviewer reset the ApprAIsal output")
                    st.rerun()
            from agents import grading
            gr3 = appraise.grade(bid, a_out, a_checks if a_ai else None)
            done3 = checklist(bid, "a3", CHECK3, heading=None, subs={0: a_out.get("reviewer_checks") or []},
                              notes={0: grading.note_html(gr3, AGENT3)})
            if done3 and not rec.get("approved_review"):
                store.save(bid, "approved_review", {"summary": b["title"], "apprAIsal": a_out.get("recommendation")}, "Reviewer approved the review")
                store.set_status(bid, "review approved")
                st.rerun()

    # Step 4: memo and letter
    with st.container(border=True):
        ui.step_header(4, "Memo & letter", "DBM format", "done" if d4 else ("now" if d3 else "lock"))
        if not d3:
            st.caption("🔒 Complete Step 3's checklist to unlock.")
            return
        ui.html('<div class="ac-step-d">The memorandum compiles the three agents\' reviewed outputs, Parts I to VII, without repeating '
                'statements. Offices, dates and the addressee are bracketed for you to complete; you confirm the recommendation.</div>')
        mf = rec.get("memo_fields")
        if not mf or "s7" not in mf or st.button("Rebuild the memo from the agents' outputs"):
            tm = rec.get("traice_memo") or {"salient": t_out.get("salient_features", ""), "related": t_out.get("related_measures_policy", "")}
            cmemo = rec.get("compaire_memo") or compaire.memo_text(c_out)
            amemo = rec.get("apprAIsal_memo") or appraise.memo_text(a_out)
            blocks = {blk.split()[0]: blk.split("\n", 1)[1] if "\n" in blk else "" for blk in amemo.split("\n\n") if blk.strip()}
            ctx = "\n".join(x for x in (t_out.get("proposal", ""), t_out.get("alignment", "")) if x)
            parts_ = appraise.harmonize(ctx, tm["salient"], tm["related"], cmemo, blocks.get("V.", ""), blocks.get("VI.", ""), blocks.get("VII.", ""))
            mf = docs.memo_prefill(bid, dict(zip(("context", "salient", "related", "comments", "fiscal", "duplication", "recommendation"), parts_)),
                                   "" if str(row.get("status_basis", "")).startswith("Derived") else row.get("status", ""),
                                   a_out.get("referrals"), rec.get("bureau_inputs"))
            store.save(bid, "memo_fields", mf, "Memo compiled from the agents' outputs")
            store.set_status(bid, "memo drafted")
            st.rerun()
        if str(mf.get("s5", "")).startswith("[Fiscal and budgetary requirements from"):
            # a memo compiled before Part V reached it: fill Part V only, keeping the reviewer's edits and confirmed recommendation
            amemo = rec.get("apprAIsal_memo") or appraise.memo_text(a_out)
            blocks = {blk.split()[0]: blk.split("\n", 1)[1] if "\n" in blk else "" for blk in amemo.split("\n\n") if blk.strip()}
            if blocks.get("V."):
                mf = dict(mf, s5=appraise.harmonize(mf.get("s4", ""), blocks["V."])[1])
                store.save(bid, "memo_fields", mf, "Part V added to the memo from ApprAIsal")
        mt1, mt2 = st.tabs(["Memorandum for the Secretary", "Letter to the committee or principal author"])
        with mt1:
            ui.html("<p><b>VII. Recommendation: confirm</b></p>")
            keys = list(appraise.OPTIONS)
            prop = a_out["recommendation"]["option"]
            pick = st.radio("Recommendation", keys, index=keys.index(prop), horizontal=True, label_visibility="collapsed",
                            format_func=lambda k: appraise.OPTIONS[k][0] + (" (proposed by ApprAIsal)" if k == prop else ""), key=f"pos_{bid}")
            prop_text = mf.get("_proposed") if pick == prop and mf.get("_proposed") else "7.1 " + appraise.OPTIONS[pick][1]
            txt = st.text_area("Part VII text", value=mf.get("s7") if docs.position_decided(mf) else prop_text, height=110, key=f"s7_{bid}_{pick}")
            if st.button("Confirm the recommendation in the memo", type="primary"):
                store.save(bid, "memo_fields", docs.set_recommendation(mf, txt), f"Reviewer confirmed the recommendation: {appraise.OPTIONS[pick][0]}")
                st.rerun()
            ek = f"edit_memo_{bid}"
            if st.button("✏️ Edit memo" if not st.session_state.get(ek) else "Close the editor", key=f"btn_{ek}"):
                st.session_state[ek] = not st.session_state.get(ek)
                st.rerun()
            if st.session_state.get(ek):
                new = field_editor(f"memo_{bid}", mf, docs.MEMO_FIELDS)
                if new:
                    store.save(bid, "memo_fields", dict(mf, **new), "Reviewer edited the memo")
                    st.session_state[ek] = False
                    st.rerun()
            for x in governance_flags(docs.memo_text(mf), "letter"):
                st.warning(x)
            paper(mf, "memo")
            st.download_button("Download memo (Word)", docs.memo_docx(mf), file_name=f"Memo_for_the_Secretary_{bid}.docx", type="primary")
        with mt2:
            if not docs.position_decided(mf):
                st.info("Confirm the recommendation in the memorandum first; the letter conveys it.")
            else:
                lf = rec.get("letter_fields")
                if not lf or st.button("Rebuild the letter from the memo"):
                    lf = docs.letter_prefill(bid, mf)
                    store.save(bid, "letter_fields", lf, "Letter pre-filled")
                    store.set_status(bid, "letter drafted")
                    st.rerun()
                lk = f"edit_letter_{bid}"
                if st.button("✏️ Edit letter" if not st.session_state.get(lk) else "Close the editor", key=f"btn_{lk}"):
                    st.session_state[lk] = not st.session_state.get(lk)
                    st.rerun()
                if st.session_state.get(lk):
                    new = field_editor(f"letter_{bid}", lf, docs.LETTER_FIELDS)
                    if new:
                        store.save(bid, "letter_fields", new, "Reviewer edited the letter")
                        st.session_state[lk] = False
                        st.rerun()
                for x in governance_flags(docs.letter_text(lf), "letter"):
                    st.warning(x)
                paper(lf, "letter")
                st.download_button("Download letter (Word)", docs.letter_docx(lf), file_name=f"Letter_{bid}.docx", type="primary")
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
    st.caption("Answers come from the bill's own text, with every citation checked." if bool(llm.api_key())
               else "Without an AI key, BILLy answers by quoting the parts of the bill that best match your question.")


def _guide_ask(q=None):
    from agents import site_guide as G
    q = (q or st.session_state.get("billy_in_guide") or "").strip()
    if not q:
        return
    hist = st.session_state.setdefault("billy_guide", [])
    hist.append({"role": "user", "content": q})
    try:
        ans = G.answer(hist[:-1], q, bool(llm.api_key()))
    except Exception as e:
        ans = f"Sorry, I couldn't answer that: {e}"
    hist.append({"role": "assistant", "content": ans})
    st.session_state["billy_in_guide"] = ""


@st.fragment
def billy_general():
    """BILLy as a guide to ActCheck when no bill is open."""
    from agents import site_guide as G
    hist = st.session_state.setdefault("billy_guide", [])
    for m in hist[-6:]:
        if m["role"] == "user":
            ui.html(f'<div class="ac-msg u">{escape(m["content"])}</div>')
        else:
            st.markdown(m["content"])
    st.caption("Ask me about ActCheck, or try one of these:" if not hist else "Ask another question:")
    for i, s_ in enumerate(G.suggestions()):
        if not any(m["content"] == s_ for m in hist):
            st.button(s_, key=f"gsug_{i}", on_click=_guide_ask, args=(s_,))
    st.text_input("Ask about ActCheck", key="billy_in_guide", placeholder="e.g. What does ApprAIsal do?", on_change=_guide_ask)
    c1, c2 = st.columns(2)
    c1.button("Ask", key="billy_go_guide", on_click=_guide_ask, type="primary")
    if hist:
        c2.button("Clear chat", key="billy_clr_guide", on_click=lambda: st.session_state.update({"billy_guide": []}))
    st.caption("To ask about a specific bill, open it in the Review workspace" + (" (log in as a reviewer first)." if not REVIEWER else "."))


def billy():
    bid = st.session_state.get("bill") if st.session_state.get("bill") in bills else None
    bill_mode = bool(bid) and page == "Review workspace"
    with st.container(key="billy"):
        with st.popover("BILLy"):
            ui.html(f'<div class="ac-billy-head"><img src="{ui.STATIC}/billy.png" alt=""><div><b>BILLy</b>'
                    f'<span>{"Your review companion · reviewing " + escape(bills[bid]["label"]) if bill_mode else "Your guide to ActCheck"}</span></div></div>')
            if bill_mode:
                billy_body(bid)
            else:
                billy_general()


# ================= pages =================
# Each page draws into its own keyed container, so switching pages replaces the previous page at once
# instead of leaving its content on screen (faded) while the new page loads.
with st.container(key="page_" + page.lower().replace(" ", "_")):
    if page == "Overview":
        ws = watch_state()
        runs = ws.get("runs", [])
        inbox_p = ROOT / "data" / "watch" / "inbox.json"
        inbox = json.loads(inbox_p.read_text()) if inbox_p.exists() else []
        last = runs[-1] if runs else {}
        c20 = cat[cat["congress"] == "20"]
        ui.hero(APP_NAME, SUBHEADING, TAGLINE, DESCRIPTION, stats=[(f"{len(cat):,}", "Bills listed, 18th to 20th Congress", "House and Senate bills from public sources", ""),
                  (f"{len(c20):,}", "Bills in the 20th Congress", f"{int((c20['chamber'] == 'House').sum()):,} House · {int((c20['chamber'] == 'Senate').sum()):,} Senate", "gold"),
                  (f"{last.get('found', 0):,}", "New bills from the daily run",
                   (f"Found on {last['time'][:10]} · {sum(1 for x in inbox if not x.get('backfill')):,} since the daily check began"
                    + (f" · {sum(1 for x in inbox if x.get('backfill')):,} older bills caught up" if any(x.get('backfill') for x in inbox) else "")
                    if last else "The daily check runs at 9:00 AM Manila time"), "red"),
                  (f"{len([k for k, _ in store.queue_list() if k in bills]):,}", "Bills slated for review",
                   "In the Review workspace, with the agents' outputs ready for the reviewer", "white")], reviewer=REVIEWER)

        ui.section("Bills by type", "What the bills propose",
                   "Bills can be grouped by whom they apply to and by what they propose to do. ActCheck assigns each bill one main type based "
                   "on its title, so the shares below are approximate.")
        which = st.radio("Congress", ["20th", "19th", "18th", "All"], horizontal=True, key="home_cong")
        d = cat if which == "All" else cat[cat["congress"] == which[:2]]
        n = max(len(d), 1)
        counts = d["type"].value_counts()
        rows = [(k, int(v), v / n) for k, v in counts.items()]
        ui.bars(rows, highlight="Government organization and mandates")
        oth = d[d["type"] == typology.OTHER]
        if len(oth):
            untitled = int((~oth["title"].map(typology.has_title)).sum())
            ui.note(f"<b>What is in 'Other or unclassified' ({len(oth):,} bills, {len(oth) / n:.1%}).</b> {untitled:,} are listed by number only: "
                    f"their title is not yet available from the source, so they cannot be typed. The other {len(oth) - untitled:,} have titles "
                    "that none of the classification rules match, usually single-subject measures worded without the key terms the rules "
                    "look for, for example recognizing the civil effects of church annulment, protecting freelancers, mandatory Bible "
                    "reading in schools or declaring maritime zones. The analyst assigns the type during review.")
        ui.html("<p style='margin:1.1rem 0 .1rem'><b>Who the bills apply to</b></p>")
        app_counts = d["applies_to"].value_counts()
        ui.stack([(k, int(app_counts.get(k, 0)), app_counts.get(k, 0) / n) for k in typology.APPLICATION], ["#0B2545", "#D4A72C", "#B8322A"])
        ui.note("<b>Why scope matters for review.</b> Under Article VI, Section 24 of the 1987 Constitution, appropriation, revenue or tariff bills, "
                "bills authorizing an increase of the public debt, bills of local application and private bills originate exclusively in the House "
                "of Representatives; the Senate may propose or concur with amendments. ActCheck flags these bills so the reviewer can follow the "
                "House version. The type in gold, government organization and mandates, is the one the agents are being tested on first.")

        ui.section("How a review flows", "From a newly filed bill to comments for legislators",
                   "A daily check finds new bills; three agents prepare the evidence; the analyst checks each step before the next one opens "
                   "and decides the position. The highlighted box at the foot of each card is what that stage hands on.")
        ui.flow2(WORKFLOW)

    elif page == "Bills":
        ui.section("Legislative measures", "Every House and Senate bill",
                   "Filter by Congress, bill type, category and status. Click a title for details. Anyone can share a <b>Report</b> on a bill with the "
                   "reviewers. Reviewers who log in can click <b>Review</b> to send a bill to the review workspace; if ActCheck does not yet have its "
                   "full text, it downloads it from the official source.")
        with st.container(border=True):
            f1, f2, f3, f4 = st.columns([0.8, 0.9, 1.6, 1.5])
            congress = f1.selectbox("Congress", ["20th", "19th", "18th", "All"])
            btype = f2.selectbox("Bill type", ["All", "House Bill", "Senate Bill"])
            ttype = f3.selectbox("Category", ["All categories"] + sorted(typology.CATEGORY_NAMES))
            statuses = ["All statuses"] + [g for g in catalogue.GROUPS if (cat["status_group"] == g).any()]
            status = f4.selectbox("Status", statuses, help="Pending, enacted, consolidated or substituted, and not enacted. Each bill shows "
                                  "its sub-heading (e.g. In the committee); the exact status from the source is in the bill's details.")
            s1, s2, s3, s4 = st.columns([2.4, 1.1, 0.9, 0.9])
            q = s1.text_input("Search bill number, title, subject, or author", placeholder="e.g. HB 2322, water resources, Villar")
            applies = s2.selectbox("Applies to", ["All"] + typology.APPLICATION)
            ledac_only = s3.toggle("LEDAC priority", value=False, help="Bills related by title to the 44 Common Legislative Agenda measures of the 20th Congress (LEDAC, 30 Sept 2025)")
            fulltext = s4.toggle("Full text only", value=False)
        df = cat
        if congress != "All":
            df = df[df["congress"] == congress[:2]]
        if btype != "All":
            df = df[df["bill_type"] == btype]
        if ttype != "All categories":
            df = df[df["type"] == ttype]
        if status != "All statuses":
            df = df[df["status_group"] == status]
        if applies != "All":
            df = df[df["applies_to"] == applies]
        if ledac_only:
            df = df[df["ledac"] != ""]
        if fulltext:
            df = df[df["reviewable"]]
        if q:
            key = q.lower().replace(" ", "")
            hay = (df["label"] + df["title"] + df["short_title"] + df["author"]).str.lower().str.replace(" ", "", regex=False)
            df = df[hay.str.contains(key, regex=False)]
        df = df.reset_index(drop=True)
        sig = (congress, btype, ttype, status, applies, ledac_only, fulltext, q)
        # before any filter is used, the list starts with the bills ActCheck recommends for review first
        recommended = sig == ("20th", "All", "All categories", "All statuses", "All", False, False, "") and not st.session_state.get("bills_all")
        if recommended:
            from pipeline import priority
            counts = {}
            for x in reports.all_reports():
                counts[x.get("bill")] = counts.get(x.get("bill"), 0) + 1
            df = priority.rank(cat, counts, 20)
            r1, r2 = st.columns([4.2, 1], vertical_alignment="center")
            r1.markdown('<div class="ac-kicker" style="margin:0">Recommended for review</div>'
                        '<div class="ac-filed">Pending 20th Congress bills with full text, ranked by how soon they may move, '
                        'strategic priority (LEDAC, FY 2027 Budget Priorities Framework), fiscal and organizational weight, likely '
                        'consolidation and public reports. Bills with the same title appear once. Use any filter to see all bills.</div>',
                        unsafe_allow_html=True)
            r2.button("Show all bills", key="bills_show_all", type="primary", on_click=lambda: st.session_state.__setitem__("bills_all", True),
                      use_container_width=True)
        elif sig == ("20th", "All", "All categories", "All statuses", "All", False, False, ""):
            st.button("← Back to the recommended bills", key="bills_show_rec", on_click=lambda: st.session_state.__setitem__("bills_all", False))
        if st.session_state.get("bills_sig") != sig:
            st.session_state["bills_sig"], st.session_state["bills_page"] = sig, 1
        per = st.session_state.get("bills_per", 20)
        pages = max(1, -(-len(df) // per))
        pg = min(st.session_state.get("bills_page", 1), pages)
        k1, k2 = st.columns([4, 1.1], vertical_alignment="bottom")
        k1.caption(f"{len(df):,} recommended bills" if recommended else f"{len(df):,} bills match · page {pg} of {pages:,}")
        k2.selectbox("Bills per page", [20, 30, 40, 50], key="bills_per")
        heads = ["Bill No.", "Title", "Bill type", "Status", "View bill", "Review"] + ([] if REVIEWER else ["Report"])
        widths = [1.0, 5.6, 1.0, 1.0, 0.8, 0.9] + ([] if REVIEWER else [0.9])
        ui.html('<div class="ac-thead" style="gap:1rem;grid-template-columns:' + " ".join(f"{w}fr" for w in widths) + '">'
                + "".join(f"<span>{h}</span>" for h in heads) + "</div>")
        with st.container(key="billgrid"):
            for _, r in df.iloc[(pg - 1) * per: pg * per].iterrows():
                r = r.to_dict()
                c = st.columns(widths, vertical_alignment="center", gap="small")
                c[0].markdown(f'<div class="ac-billno">{escape(r["label"])}</div>', unsafe_allow_html=True)
                title = r["title"] or r["short_title"] or "(title not yet available)"
                for ch in "*_[]`#<>":
                    title = title.replace(ch, "\\" + ch)
                if c[1].button(title, key=f"t_{r['id']}", type="tertiary"):
                    bill_dialog(r)
                c[1].markdown(f'<div class="ac-filed">Filed {escape(r["date_filed"] or "(date not clearly visible; verify in file)")}'
                              + (f' · Principal author: <b>{escape(r["author"])}</b>' if r.get("author") else "")
                              + (" · full text" if r["reviewable"] else "")
                              + (f' · <b style="color:#B3261E">LEDAC priority</b>' if r.get("ledac") else "") + "</div>", unsafe_allow_html=True)
                if recommended and r.get("why"):
                    c[1].markdown('<div class="ac-why"><b>Why review first:</b> ' + escape(r["why"]) + "</div>", unsafe_allow_html=True)
                c[2].markdown(r["bill_type"])
                c[3].markdown(f'<span class="ac-badge {STATUS_COLOR.get(r["status_group"], "")}">{escape(r["status_group"])}</span>'
                              f'<div class="ac-filed" style="margin-top:.25rem"><b>{escape(r["status_sub"])}</b></div>', unsafe_allow_html=True)
                if r["source_url"]:
                    c[4].markdown(f'<div class="ac-view"><a href="{escape(r["source_url"])}" target="_blank">PDF ↗</a></div>', unsafe_allow_html=True)
                if REVIEWER:
                    if c[5].button("Review", key=f"r_{r['id']}"):
                        start_review(r)
                else:
                    c[5].button("Log In", key=f"li_{r['id']}", on_click=check_in, help="Reviewer log in (no password for this course prototype)")
                    if c[6].button("Report", key=f"rp_{r['id']}"):
                        report_dialog(r)
        p1, p2, p3 = st.columns([1, 2, 1])
        p3 = p3.container(key="pg_next")
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
        with left, st.container(key="qside"):
            rail = st.empty()                    # filled after the case renders, when its step states are known
            ui.html('<div class="ac-kicker" style="margin-top:1.2rem">Bills under review</div>')
            if not queue:
                st.caption("No bills yet. Click Review on the Bills page.")
            for k, r in queue:
                active = k == st.session_state.get("bill")
                # the bill being reviewed is highlighted; the others in line are dimmed until opened
                with st.container(border=True, key=("qactive_" if active else "qcard_") + k.replace("-", "_")):
                    t1, t2 = st.columns([5, 1], vertical_alignment="top")
                    with t1:
                        if active:
                            ui.html('<div class="ac-qnow">Now reviewing</div>')
                        st.markdown(f"**{bills[k]['label']}** · {bills[k]['congress']}th")
                    with t2, st.container(key=f"qx_{k.replace('-', '_')}"):
                        if st.button("✕", key=f"x_{k}", help="Remove this bill from the workspace (its saved work is kept and returns if you review it again)"):
                            store.unqueue(k)
                            if active:
                                st.session_state.pop("bill", None)
                            st.rerun()
                    st.caption(f"{bills[k]['title'][:80]}… · {r.get('status', 'new')}")
                    if not active and st.button("Open", key=f"q_{k}", use_container_width=True):
                        st.session_state["bill"] = k
                        st.rerun()
        with right:
            bid = st.session_state.get("bill")
            if not bid or bid not in bills:
                ui.notice("No bill open. Go to <b>Bills</b> and click <b>Review</b> on any bill.", "navy")
            else:
                store.queue(bid)
                st.session_state.pop("_rail", None)
                case(bid)
                if st.session_state.get("_rail"):
                    lab, states = st.session_state["_rail"]
                    rail.markdown(ui.progress_rail(lab, [AGENT1, AGENT2, AGENT3, "Memo & letter"], STEP_DESCS, states),
                                  unsafe_allow_html=True)

    elif page == "Library":
        ui.section("Document library", "What ActCheck reads and relies on",
                   "Choose a collection. Review References are the public documents behind ActCheck's costing, policy context, process and "
                   "safeguards. Full Text of Bills holds the bills, committee reports and laws ActCheck has read, divided into sections so each "
                   "finding can point to the exact provision.")
        import csv as _csv
        refs = list(_csv.DictReader(open(ROOT / "data" / "reference" / "review_references.csv", newline="")))
        view = st.session_state.get("lib_view", "refs")
        bill_docs = {k: v for k, v in bills.items() if v.get("kind") != "reference"}
        ref_docs = {k: v for k, v in bills.items() if v.get("kind") == "reference"}
        t1, t2 = st.columns(2)
        with t1:
            with st.container(border=True, key="tile_refs" + ("_on" if view == "refs" else "")):
                ui.html(f'<div class="ac-tile"><span class="ac-aico">{svg("book", 28)}</span><div><div class="ac-fk">Collection 1</div>'
                        f'<div class="ac-aname">Review References</div><p>{len(refs)} public documents: budget and audit data, policy context, '
                        'process, governance and legislative data sources, each with its date and purpose.</p></div></div>')
                if st.button("Open Review References", key="open_refs", use_container_width=True, type="primary" if view == "refs" else "secondary"):
                    st.session_state["lib_view"] = "refs"
                    st.rerun()
        with t2:
            with st.container(border=True, key="tile_bills" + ("_on" if view == "bills" else "")):
                ui.html(f'<div class="ac-tile"><span class="ac-aico">{svg("files", 28)}</span><div><div class="ac-fk">Collection 2</div>'
                        f'<div class="ac-aname">Full Text of Bills</div><p>{len(bill_docs):,} documents read by ActCheck (bills, committee reports '
                        'and laws), split into sections for citation and checking.</p></div></div>')
                if st.button("Open Full Text of Bills", key="open_bills", use_container_width=True, type="primary" if view == "bills" else "secondary"):
                    st.session_state["lib_view"] = "bills"
                    st.rerun()
        if view == "refs":
            groups = list(dict.fromkeys(r["Group"] for r in refs))
            text_of = {"Expenditure Priorities": "REF-BPF2027-EXP", "Macroeconomic and Fiscal": "REF-BPF2027-MACRO",
                       "Summary Inflation Report": "REF-PSA-CPI-OCT2026", "Common Legislative Agenda": "REF-LEDAC-CLA20"}

            def ref_doc(title):
                return next((v for k, v in text_of.items() if k in title and v in ref_docs), None)
            for g in groups:
                ui.html(f"<p style='margin:1rem 0 .2rem'><b>{escape(g)}</b></p>")
                rows_g = [r for r in refs if r["Group"] == g]
                if not any(ref_doc(r["Title"]) for r in rows_g):
                    ui.table(["Title", "Issued by", "Released", "Purpose in ActCheck"],
                             [[f'<a href="{escape(r["Link"])}" target="_blank">{escape(r["Title"])} ↗</a>', escape(r["Issued by"]),
                               escape(r["Released"]), escape(r["Purpose in ActCheck"])] for r in rows_g], cls="refs")
                    continue
                # documents whose text ActCheck reads: same table, with a Read button beside the title
                widths = [3.1, 0.75, 2.0, 1.2, 2.8]
                with st.container(key="refgrid"):
                    ui.html('<div class="ac-thead refhead" style="grid-template-columns:' + " ".join(f"{w}fr" for w in widths) + '">'
                            '<span style="grid-column:span 2">Title</span><span>Issued by</span><span>Released</span><span>Purpose in ActCheck</span></div>')
                    for r in rows_g:
                        c = st.columns(widths, vertical_alignment="center", gap="small")
                        k = ref_doc(r["Title"])
                        c[0].markdown(f'<a class="ac-reflink" href="{escape(r["Link"])}" target="_blank">{escape(r["Title"])} ↗</a>', unsafe_allow_html=True)
                        if k and c[1].button("📖 Read", key=f"refread_{k}", help="Read the text ActCheck uses, section by section"):
                            doc_dialog(k)
                        c[2].markdown(f'<div class="ac-refcell">{escape(r["Issued by"])}</div>', unsafe_allow_html=True)
                        c[3].markdown(f'<div class="ac-refcell">{escape(r["Released"])}</div>', unsafe_allow_html=True)
                        c[4].markdown(f'<div class="ac-refcell">{escape(r["Purpose in ActCheck"])}</div>', unsafe_allow_html=True)
                ui.html("<div class='ac-refnote'><b>Note:</b> 📖 Read opens the text ActCheck keeps of these documents. They are split into "
                        "sections so ApprAIsal can quote them in a review, and each quote is checked against this text, as with bills.</div>")
            st.caption("Titles open the document at its official source, or a copy kept with ActCheck where no stable public link was found. "
                       "Internal DBM papers are not part of this library.")
        else:
            rank = {"House Bill": 0, "Senate Bill": 1, "Substitute bill": 2, "Committee report": 3, "Law": 4}
            lib = sorted(bill_docs.values(), key=lambda b: (rank.get(doc_type(b), 5), -int(b.get("congress") or 0),
                                                         -int((re.findall(r"\d+", str(b.get("label", ""))) or ["0"])[0]), str(b.get("label", ""))))
            l1, l2, l3 = st.columns([2.4, 1.2, 1.4])
            lq = l1.text_input("Search document number or title", key="lib_q", placeholder="e.g. HB 6789, water resources")
            types = sorted({doc_type(b) for b in lib})
            lt = l2.selectbox("Type", ["All types"] + types, key="lib_type")
            grps = sorted({doc_group(b) for b in lib})
            lg = l3.selectbox("Group", ["All groups"] + grps, key="lib_group")
            if lq.strip():
                ql = lq.strip().lower()
                lib = [b for b in lib if ql in f"{b.get('label', '')} {b.get('title', '')} {b.get('id', '')}".lower()]
            if lt != "All types":
                lib = [b for b in lib if doc_type(b) == lt]
            if lg != "All groups":
                lib = [b for b in lib if doc_group(b) == lg]
            sig = (lq, lt, lg)
            if st.session_state.get("lib_sig") != sig:
                st.session_state["lib_sig"], st.session_state["lib_page"] = sig, 1
            per = st.session_state.get("lib_per", 20)
            pages = max(1, -(-len(lib) // per))
            pg = min(st.session_state.get("lib_page", 1), pages)
            k1, k2 = st.columns([4, 1.1], vertical_alignment="bottom")
            k1.caption(f"{len(lib):,} documents · page {pg} of {pages:,} · click a title to read it section by section")
            k2.selectbox("Documents per page", [20, 30, 40, 50], key="lib_per")
            heads = ["Document No.", "Title", "Type", "No. of sections", "Text type", "Group"]
            widths = [1.15, 5.0, 1.25, 0.85, 1.1, 1.55]
            ui.html('<div class="ac-thead" style="grid-template-columns:' + " ".join(f"{w}fr" for w in widths) + '">'
                    + "".join(f"<span>{h}</span>" for h in heads) + "</div>")
            with st.container(key="libgrid"):
                for b in lib[(pg - 1) * per: pg * per]:
                    c = st.columns(widths, vertical_alignment="center")
                    c[0].markdown(f'<div class="ac-billno">{escape(str(b.get("label", "")))}</div>'
                                  + (f'<div class="ac-filed">{b["congress"]}th Congress</div>' if b.get("congress") else ""), unsafe_allow_html=True)
                    title = b.get("title") or "(title not found in the text)"
                    for ch in "*_[]`#<>":
                        title = title.replace(ch, "\\" + ch)
                    if c[1].button(title, key=f"lt_{b['id']}", type="tertiary"):
                        doc_dialog(b["id"])
                    c[2].markdown(f'<div style="font-size:.9rem;word-break:normal;overflow-wrap:normal">{escape(doc_type(b))}</div>', unsafe_allow_html=True)
                    c[3].markdown(f'<div class="ac-billno" style="font-weight:600">{b.get("n_sections") or 0}</div>', unsafe_allow_html=True)
                    c[4].markdown("Scanned (recognized)" if b.get("text_source") == "ocr" else "PDF text")
                    c[5].markdown(f'<div style="font-size:.85rem">{escape(doc_group(b))}</div>', unsafe_allow_html=True)
            p1, p2, p3 = st.columns([1, 2, 1])
            p3 = p3.container(key="pg_next_lib")
            if p1.button("← Previous", disabled=pg <= 1, key="lib_prev"):
                st.session_state["lib_page"] = pg - 1
                st.rerun()
            p2.markdown(f"<div style='text-align:center;padding-top:.4rem'>Page {pg} of {pages:,}</div>", unsafe_allow_html=True)
            if p3.button("Next →", disabled=pg >= pages, key="lib_next"):
                st.session_state["lib_page"] = pg + 1
                st.rerun()
            if st.session_state.get("open_doc") in bills:
                doc_dialog(st.session_state.pop("open_doc"))

    elif page == "Run log":
        from datetime import datetime, timedelta, timezone

        def manila(t, fmt="%d %b %Y, %I:%M %p"):
            try:
                d = datetime.fromisoformat(str(t).replace("Z", "+00:00"))
                return (d.astimezone(timezone(timedelta(hours=8)))).strftime(fmt).lstrip("0")
            except Exception:
                return str(t)[:16]

        # 1. Public reports
        rep_all = reports.all_reports()
        ui.section("Public reports", "Inputs shared by civil society and others from the Bills page",
                   f"{len(rep_all)} report(s) received. Click a title to read the report"
                   + ("." if REVIEWER else " (reviewers only; log in at the top right). Contact details are never shown publicly."))
        widths = [1.0, 5.2, 2.2, 1.4]
        ui.html('<div class="ac-thead" style="grid-template-columns:' + " ".join(f"{w}fr" for w in widths) + '">'
                + "".join(f"<span>{h}</span>" for h in ["Bill No.", "Title", "Topic", "Received"]) + "</div>")
        with st.container(key="libgrid"):
            if not rep_all:
                c = st.columns(widths, vertical_alignment="center")
                c[0].markdown('<div class="ac-filed">—</div>', unsafe_allow_html=True)
                c[1].markdown('<div class="ac-filed" style="font-size:.88rem">No public reports yet. Reports sent with the Report button '
                              'on the Bills page will be listed here.</div>', unsafe_allow_html=True)
            for k, x in enumerate(rep_all):
                c = st.columns(widths, vertical_alignment="center", gap="small")
                c[0].markdown(f'<div class="ac-billno">{escape(x.get("label", ""))}</div>', unsafe_allow_html=True)
                t = (x.get("title") or "(title not given)")
                for ch in "*_[]`#<>":
                    t = t.replace(ch, "\\" + ch)
                if c[1].button(t, key=f"rl_rep_{k}", type="tertiary"):
                    if REVIEWER:
                        reports_dialog([x], f"{x.get('label', '')}: public report")
                    else:
                        st.toast("Reports are visible to reviewers only. Log in at the top right.")
                cat_ = x.get("category", "")
                c[2].markdown(f'<div style="font-size:.85rem">{escape(cat_.split(":", 1)[-1].strip() if ":" in cat_ else cat_)}</div>', unsafe_allow_html=True)
                c[3].markdown(f'<div style="font-size:.85rem">{escape(manila(x.get("time", ""), "%d %b %Y"))}</div>', unsafe_allow_html=True)
        if REVIEWER:
            state, msg = reports.sheet_status()
            st.caption(("✅ " if state == "connected" else "⚠️ ") + msg)

        # 2. Data sources and the daily check
        runs = watch_state().get("runs", [])
        last_run = manila(runs[-1]["time"]) if runs else "not yet run"
        ui.section("Data sources and daily check", "Where ActCheck gets its bills, and when each source was last checked",
                   f"The daily check runs every day at 9:00 AM (Manila) on GitHub's servers; latest run: {last_run}. "
                   "A source that refuses automated visitors is never bypassed.")
        roles = {
            "House of Representatives: legislative documents page": "Official House list of bills (reference)",
            "House of Representatives: documents server (bill PDFs)": "Daily check for newly filed House bills and their full text; catch-up of older bills",
            "Senate: bill listing": "Senate bills, authors and status (refreshed every Monday)",
            "BetterGov.PH Open Congress Data (dataset 4)": "Bill list, titles, status and authors, 18th to 20th Congress (daily)",
            "BetterGov.PH Philippine Legal Documents Library (dataset 24)": "Republic Acts and their summaries, used for enacted status (every Monday)",
        }
        srcp = ROOT / "data" / "watch" / "sources.json"
        srows = json.loads(srcp.read_text()) if srcp.exists() else []
        ui.table(["Source", "Role in ActCheck", "Last checked"],
                 [[f'<a href="{escape(r["url"])}" target="_blank">{escape(r["source"])}</a>', escape(roles.get(r["source"], r.get("role", ""))),
                   escape(manila(r["time"], "%d %b %Y"))] for r in srows], cls="src")

        # 3. Agent runs
        order = {"TrAIce": 1, "CompAIre": 2, "ApprAIsal (draft review)": 3, "ApprAIsal (second-reviewer check)": 4,
                 "ApprAIsal (memo)": 5, "ApprAIsal (letter)": 6}
        names = {"p1": AGENT1, "p2": AGENT2}
        agg = {}
        for f in sorted((ROOT / "logs").glob("*.jsonl")):
            for x in f.read_text().splitlines():
                try:
                    d = json.loads(x)
                except ValueError:
                    continue
                bid = d.get("target") or d.get("bill")
                if not bid:
                    continue
                key = f.stem.split("_")[0]
                if key in names:
                    agent = names[key]
                else:
                    stp = str(d.get("step") or (d.get("meta") or {}).get("step") or "review")
                    agent = {"review": "ApprAIsal (draft review)", "redteam": "ApprAIsal (second-reviewer check)",
                             "memo": "ApprAIsal (memo)", "letter": "ApprAIsal (letter)"}.get(stp, "ApprAIsal (draft review)")
                a = agg.setdefault(bid, {"agent": agent, "time": ""})
                if order.get(agent, 0) > order.get(a["agent"], 0):
                    a["agent"] = agent
                a["time"] = max(a["time"], str(d.get("time") or (d.get("meta") or {}).get("time") or ""))
        ui.section("Agent runs", "Bills the agents have worked on",
                   "The furthest step each bill has reached and when an agent last ran on it.")
        ui.table(["Bill No.", "Title", "Ran up to", "Last run"],
                 [[f'<b>{escape(bills[b]["label"] if b in bills else b)}</b>', escape((bills.get(b) or {}).get("title", "")),
                   escape(v["agent"]), escape(manila(v["time"]))]
                  for b, v in sorted(agg.items(), key=lambda kv: kv[1]["time"], reverse=True)]
                 or [["—", "No agent runs yet.", "", ""]], cls="runs")

        # 4. Portfolio and project log
        pl = ROOT / "docs" / "PROJECT_LOG.md"
        if pl.exists():
            with st.expander("Agentic AI Portfolio and Project Log"):
                st.markdown(pl.read_text().split("\n", 1)[1])

    else:
        import howitworks
        howitworks.render(AGENT1, AGENT2, AGENT3, WORKFLOW)

ui.footer(APP_NAME, LABEL)
billy()
