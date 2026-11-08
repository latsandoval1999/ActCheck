"""ActCheck reviewer portal: every House and Senate bill, with AI-assisted preliminary review.

    streamlit run app/streamlit_app.py

Pages: Home (daily check, headline numbers) -> Bills (every bill, filters, open one) ->
Review workspace (one-click review; TrAIce, CompAIre, AppraisAI tabs; comments, report, memo and
letter) -> Ask ActCheck (grounded chat) -> Library -> Run log -> About.

Scope: every bill is listed. The agents are tuned and tested on the pilot scope (bills that create a
national government entity); other bills with full text can be reviewed experimentally.

Without an API key every rules-only part works, and each agent can be run through the free
route: download its prompt, run it in a Claude chat, paste the reply back to check and save it.
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

from agents import llm, store  # noqa: E402
from agents.names import APP_NAME, APP_TAGLINE, AGENT1, AGENT2, AGENT3  # noqa: E402
from pipeline import catalogue  # noqa: E402
from pipeline.compare import load, related_bills  # noqa: E402
import ui  # noqa: E402

LABEL = "AI-assisted preliminary draft for DBM reviewer validation. Not an official position."
PILOT = "Creates a national agency (pilot)"
st.set_page_config(page_title=f"{APP_NAME} · Bill monitoring and preliminary review", page_icon="⚖️", layout="wide",
                   initial_sidebar_state="collapsed")
ui.inject()
bills, secs = load()
PAGES = ["Home", "Bills", "Review workspace", "Ask ActCheck", "Library", "Run log", "About"]


@st.cache_data(show_spinner="Loading the bill list...")
def bill_table(stamp):
    return pd.DataFrame(catalogue.build(stamp))


# ---------------- helpers ----------------
def go(page, bill=None):
    """Navigate on the next run (widget state can only be changed before widgets are drawn)."""
    if bill:
        st.session_state["bill"] = bill
    st.session_state["_goto"] = page
    st.rerun()


def check_table(checks):
    if not checks:
        return
    df = pd.DataFrame(checks)
    st.dataframe(df, use_container_width=True, hide_index=True)
    if "check" in df:
        bad = int((df["check"] != "verified").sum())
        (st.error if bad else st.success)(f"{len(df) - bad} of {len(df)} citations verified against the source text.")


def pick(df, key, column_config=None, height=None):
    """Single-row selection from a dataframe; returns the row position or None."""
    kw = {"height": min(height, 38 + 35 * max(len(df), 1))} if height else {}
    ev = st.dataframe(df, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row",
                      key=key, column_config=column_config, **kw)
    rows = ev.selection.rows if ev and hasattr(ev, "selection") else []
    return rows[0] if rows else None


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
        reply = st.text_area("Paste the reply", key=f"reply_{key}", height=150)
        if st.button("Check and save reply", key=f"save_{key}", disabled=not reply.strip()):
            try:
                on_reply(llm.parse_json(reply) if json_reply else reply)
                st.success("Checked and saved.")
                st.rerun()
            except Exception as e:
                st.error(f"Could not read the reply: {e}")


def pick_reference(bid, research_out):
    order = ("consolidated", "counterpart", "near-copy", "earlier version", "competing")
    if research_out:
        for lab in order:
            for r in research_out.get("related", []):
                if lab in (r.get("relationship") or "") and r.get("id") in bills and r["id"] != bid:
                    return r["id"]
    rel = related_bills(bid, top=1)
    return rel[0]["id"] if rel else None


def watch_state():
    p = ROOT / "data" / "watch" / "state.json"
    return json.loads(p.read_text()) if p.exists() else {}


def bill_badges(row):
    items = [(f"{row['chamber']} · {row['congress']}th Congress", "navy")]
    items.append((row["scope"], "pilot" if row["scope"] == PILOT else ""))
    items.append((row["text"], "good" if row["text"] == "Full text" else ""))
    if row.get("status"):
        items.append((row["status"], ""))
    ui.badges(items)


TABLE_COLS = {"label": "Bill", "congress": "Congress", "date_filed": "Filed", "title_show": "Title", "status": "Status",
              "scope": "Scope", "text": "Text", "source_url": "Source"}
TABLE_CFG = {
    "Source": st.column_config.LinkColumn("Source", display_text="Open", width="small"),
    "Title": st.column_config.TextColumn("Title", width="large"),
    "Bill": st.column_config.TextColumn("Bill", width="small"),
    "Congress": st.column_config.TextColumn("Congress", width="small"),
}


def show_table(df):
    t = df.assign(title_show=df["short_title"].where(df["short_title"].astype(bool), df["title"]).str.slice(0, 220))
    return t[list(TABLE_COLS)].rename(columns=TABLE_COLS)


def bill_panel(row):
    """Details of one selected bill, with the next action."""
    with st.container(border=True):
        st.markdown(f"#### {escape(row['label'])} · {row['congress']}th Congress")
        bill_badges(row)
        ui.html(f'<div class="ac-billtitle">{escape(row["title"] or row["short_title"] or "(title not yet available)")}</div>')
        meta = [("Filed", row["date_filed"]), ("Committee", row["committee"]), ("Author", row["author"]),
                ("Listed from", row["source"])]
        st.caption(" · ".join(f"{k}: {v}" for k, v in meta if v))
        c1, c2 = st.columns([1, 1])
        if row["reviewable"]:
            if c1.button("Open review workspace", type="primary", key=f"open_{row['id']}"):
                go("Review workspace", row["id"])
            if row["scope"] != PILOT:
                st.caption("Outside the pilot scope: the agents can run, but they are tuned for bills that create a national agency.")
        else:
            c1.button("Open review workspace", disabled=True, key=f"open_{row['id']}",
                      help="The full text of this bill is not yet in ActCheck.")
            st.caption("The bill's full text is not yet in ActCheck. The daily check downloads new bills automatically; "
                       "older ones can be added with the downloader (see README).")
        if row["source_url"]:
            c2.link_button("View source document", row["source_url"])


# ---------------- sidebar (reviewer settings) ----------------
if "_goto" in st.session_state:  # apply navigation requested on the previous run
    st.session_state["nav"] = st.session_state.pop("_goto")
    for k in ("home_tbl", "bills_tbl"):  # clear table selections so they don't re-trigger
        st.session_state.pop(k, None)
st.session_state.setdefault("nav", "Home")
with st.sidebar:
    st.markdown("### Reviewer settings")
    pasted = st.text_input("Anthropic API key (optional, kept for this session only)", type="password")
    if pasted:
        st.session_state["user_api_key"] = pasted
    live = bool(llm.api_key())
    st.write("AI agents:", "**on**" if live else "**off** (rules-only checks and free route)")
    if st.session_state.get("bill") in bills:
        b = bills[st.session_state["bill"]]
        st.info(f"Open bill: **{b['label']}** ({b['congress']}th)\n\nStatus: {store.load(b['id']).get('status', 'new')}")
    st.caption(LABEL)

ui.header(APP_NAME, APP_TAGLINE)
page = st.radio("Navigation", PAGES, key="nav", horizontal=True, label_visibility="collapsed")
cat = bill_table(catalogue.stamp())


# ---------------- Home ----------------
if page == "Home":
    ws = watch_state()
    runs = ws.get("runs", [])
    inbox_path = ROOT / "data" / "watch" / "inbox.json"
    inbox = json.loads(inbox_path.read_text()) if inbox_path.exists() else []
    statuses = store.all_status()
    c20 = cat[cat["congress"] == "20"]
    ui.hero("Legislative measures monitor",
            "Every bill, checked before it becomes an Act",
            "ActCheck lists House and Senate bills, checks both chambers every morning for new filings, and helps a budget "
            "reviewer prepare a sourced preliminary review: legislative history, comparison with related measures, "
            "cost range and draft comments.",
            [(f"{len(cat):,}", "Bills listed, 18th–20th Congress"), (f"{len(c20):,}", "Bills in the 20th Congress"),
             (f"{int((cat['scope'] == PILOT).sum()):,}", "Create a national agency (pilot scope)"),
             (f"{int(cat['reviewable'].sum()):,}", "With full text, ready to review")])
    if runs:
        last = runs[-1]
        err = "; ".join(f"{k}: {v}" for k, v in (last.get("errors") or {}).items())
        ui.notice("Daily check", f"Last run <b>{escape(last['time'][:16].replace('T', ' '))} UTC</b>: "
                  f"<b>{last.get('found', 0)}</b> new bills found"
                  + (f", {last.get('pilot_scope', 0)} in the pilot scope" if "pilot_scope" in last else "")
                  + (f". <br>Problems: {escape(err)}" if err else ". Runs every day at 06:17 Manila time."))
    else:
        ui.notice("Daily check", "The daily check has not run yet. It runs every morning at 06:17 Manila time on GitHub.", "info")

    ui.section("Newly filed bills", "Found by the daily check on the House and Senate websites. Select a row to see details.")
    if inbox:
        new = cat[cat["id"].isin([x["id"] for x in inbox])].copy()
        new = new.sort_values(["found", "number"], ascending=False).head(200).reset_index(drop=True)
        only = st.toggle("Show only bills in the pilot scope (create a national agency)", value=False)
        if only:
            new = new[new["scope"] == PILOT].reset_index(drop=True)
        i = pick(show_table(new), "home_tbl", TABLE_CFG, height=320)
        if i is not None:
            bill_panel(new.iloc[i].to_dict())
    else:
        st.info("No new bills yet. Browse every bill on the Bills page.")

    ui.section("How a review works", "Three agents prepare drafts; the reviewer checks, edits and decides.")
    a, b, c = st.columns(3)
    with a:
        ui.card(AGENT1, "Traces the bill's history: earlier and parallel versions in both chambers, refiled bills and the "
                "existing laws it touches. Runs the daily check.", 1)
    with b:
        ui.card(AGENT2, "Compares the bill with the closest related measure, section by section: the problem it addresses, "
                "substantial differences and design options.", 2)
    with c:
        ui.card(AGENT3, "Appraises cost (from a rules-based costing engine), risks and overlaps, and drafts preliminary "
                "comments, a memo and a letter for the reviewer to finalise.", 3)
    ui.section("Reviews in progress")
    if statuses:
        rows = [{"Bill": bills[k]["label"] if k in bills else k, "Congress": bills[k]["congress"] if k in bills else "",
                 "Status": v, "id": k} for k, v in statuses.items()]
        df = pd.DataFrame(rows)
        for _, r in df.iterrows():
            cc1, cc2, cc3 = st.columns([2, 2, 1])
            cc1.markdown(f"**{r['Bill']}** · {r['Congress']}th Congress")
            cc2.markdown(f"Status: {r['Status']}")
            if cc3.button("Open", key=f"rv_{r['id']}"):
                go("Review workspace", r["id"])
    else:
        st.caption("No reviews started yet.")


# ---------------- Bills ----------------
elif page == "Bills":
    ui.section("Legislative measures", "Every House and Senate bill ActCheck knows about. Filter, then select a row.")
    with st.container(border=True):
        f1, f2, f3, f4 = st.columns([1, 1, 1.4, 1])
        congress = f1.selectbox("Congress", ["20th", "19th", "18th", "All"])
        chamber = f2.selectbox("Chamber", ["Both", "House", "Senate"])
        scope = f3.selectbox("Scope", ["All bills", PILOT, "Other legislation", "Local office or facility"])
        text = f4.selectbox("Text", ["Any", "Full text", "Listing only", "Text pending"])
        s1, s2 = st.columns([3, 1])
        q = s1.text_input("Search bill number, title or subject", placeholder="e.g. HB 2322, water resources, coast guard")
        status = s2.text_input("Status contains", placeholder="e.g. committee")
    df = cat
    if congress != "All":
        df = df[df["congress"] == congress[:2]]
    if chamber != "Both":
        df = df[df["chamber"] == chamber]
    if scope != "All bills":
        df = df[df["scope"] == scope]
    if text != "Any":
        df = df[df["text"] == text]
    if status:
        df = df[df["status"].str.contains(status, case=False, na=False)]
    if q:
        key = q.lower().replace(" ", "")
        hay = (df["label"] + df["title"] + df["short_title"]).str.lower().str.replace(" ", "", regex=False)
        df = df[hay.str.contains(key, regex=False)]
    df = df.reset_index(drop=True)
    st.caption(f"{len(df):,} bills match · House bills from the House documents server and Open Congress Data; Senate bills "
               "from the Senate website listing. Lists are refreshed by the daily check.")
    i = pick(show_table(df), "bills_tbl", TABLE_CFG, height=480)
    if i is not None:
        bill_panel(df.iloc[i].to_dict())


# ---------------- Review workspace ----------------
elif page == "Review workspace":
    bid = st.session_state.get("bill")
    if not bid or bid not in bills:
        ui.notice("No bill open", "Open a bill with full text from the <b>Home</b> or <b>Bills</b> page.", "info")
        st.stop()
    from agents.research import evidence_pack, brief_markdown, build_messages as p1_msgs, check_output as p1_check
    from agents.diagnosis import fact_diff, report_markdown as p2_md, build_messages as p2_msgs, check_output as p2_check
    from agents.costing import cost_range, peso
    from agents.appraisal import (review_markdown, check_review, check_document, POSITION_PLACEHOLDER,
                                  build_review_messages, build_redteam_messages, build_memo_messages, build_letter_messages)
    b = bills[bid]
    rec = store.load(bid)
    row = cat[cat["id"] == bid]
    row = row.iloc[0].to_dict() if len(row) else None
    ui.html(f'<div class="ac-crumb">Bills / <b>{escape(b["label"])}</b></div>')
    st.markdown(f"## {escape(b['label'])} · {b['congress']}th Congress")
    if row:
        bill_badges(row)
    ui.html(f'<div class="ac-billtitle">{escape(b["title"])}</div>')
    status = rec.get("status", "new")
    ui.steps(store.STATUSES, status)
    st.caption(f"Text: {b['text_source']} ({b['n_sections']} sections)"
               + (" · OCR text: check quotes against the PDF" if b["text_source"] == "ocr" else ""))
    if row and row["scope"] != PILOT:
        ui.notice("Outside the pilot scope", f"This bill does not appear to create a national agency. {AGENT1} and {AGENT2} "
                  f"work on any bill; {AGENT3}'s costing engine is built for new agencies, so treat its cost range as not applicable.")

    research_out = (rec.get("research") or {}).get("output")
    cand = [r["id"] for r in related_bills(bid, top=15)]
    default_ref = pick_reference(bid, research_out) or (cand[0] if cand else None)
    if default_ref and default_ref not in cand:
        cand = [default_ref] + cand
    ref = st.selectbox(f"Compare with ({AGENT2} reference)", cand,
                       index=cand.index(rec.get("reference", default_ref)) if rec.get("reference", default_ref) in cand else 0,
                       format_func=lambda x: f"{bills[x]['label']} ({bills[x]['congress']}th) · {bills[x]['title'][:90]}")

    if st.button(f"▶ Run full review ({AGENT1}, {AGENT2}, {AGENT3} and red-team)", type="primary", disabled=not live):
        from agents.research import run_agent as run1
        from agents.diagnosis import run_agent as run2
        from agents.appraisal import run_review, run_redteam
        with st.status("Running full review...", expanded=True) as s:
            try:
                s.write(f"{AGENT1}: legislative history, related measures, existing laws...")
                r1 = run1(bid)
                store.save(bid, "research", {"output": r1["output"], "checks": r1["checks"]}, f"{AGENT1} run")
                ref = pick_reference(bid, r1["output"]) or ref
                s.write(f"{AGENT2}: comparing with {bills[ref]['label']}...")
                r2 = run2(bid, ref)
                store.save(bid, "diagnosis", {"output": r2["output"], "checks": r2["checks"], "reference": ref}, f"{AGENT2} run")
                store.save(bid, "reference", ref)
                s.write(f"{AGENT3}: preliminary review and comments...")
                r3 = run_review(bid, r1["output"], r2["output"])
                store.save(bid, "review", {"output": r3["draft"], "checks": r3["checks"]}, f"{AGENT3} review")
                s.write("Red-teamer: independent check of the review...")
                rt = run_redteam(bid, r3["draft"])
                store.save(bid, "redteam", {"output": rt["redteam"]}, "Red-team run")
                store.set_status(bid, "in review")
                s.update(label="Full review complete. Check each tab before approving.", state="complete")
            except Exception as e:
                s.update(label=f"Stopped: {e}", state="error")
        st.rerun()
    if not live:
        st.caption("AI agents are off (add a key under Reviewer settings, top-left ›). Each tab shows the rules-only "
                   "analysis and a free route to run the agent in a Claude chat.")

    t1, t2, t3, t4, t5 = st.tabs([f"1 · {AGENT1} · Evidence", f"2 · {AGENT2} · Comparison", f"3 · {AGENT3} · Appraisal",
                                  "Comments & report", "Memo & letter"])

    with t1:
        pack = evidence_pack(bid)
        if research_out:
            st.markdown(brief_markdown(pack, research_out, rec["research"].get("checks")))
            check_table(rec["research"].get("checks"))
        else:
            st.markdown(brief_markdown(pack))
        free_route(f"p1_{bid}", lambda: p1_msgs(bid)[:2],
                   lambda out: (store.save(bid, "research", {"output": out, "checks": p1_check(out)}, f"{AGENT1} (free route)"),
                                store.set_status(bid, "in review")))

    with t2:
        dia = rec.get("diagnosis") or {}
        if dia and dia.get("reference") == ref:
            st.markdown(p2_md(bid, ref, dia["output"], dia.get("checks")))
            check_table((dia.get("checks") or {}).get("citations"))
        else:
            fact_diff(bid, ref)
            st.markdown(p2_md(bid, ref))
            if dia:
                st.caption(f"A saved {AGENT2} run exists against {dia.get('reference')}; choose it above to view.")
        free_route(f"p2_{bid}_{ref}", lambda: p2_msgs(bid, ref)[:2],
                   lambda out: (store.save(bid, "diagnosis", {"output": out, "checks": p2_check(out, bid, ref), "reference": ref}, f"{AGENT2} (free route)"),
                                store.save(bid, "reference", ref)))

    with t3:
        cost = cost_range(bid)
        c1, c2, c3 = st.columns(3)
        c1.metric("Entity type (rule)", cost["entity_type"])
        c2.metric("First-year range (costing engine)", f"{peso(cost['range']['low'])} – {peso(cost['range']['high'])}")
        c3.metric("Amount stated in the bill", ", ".join(peso(x["pesos"]) for x in cost["stated_in_bill"]) or "none")
        with st.expander("Costing assumptions and comparators"):
            st.dataframe(pd.DataFrame(cost["assumptions"]), use_container_width=True, hide_index=True)
            st.dataframe(pd.DataFrame(cost["method_b_comparators"]["comparators"]), use_container_width=True, hide_index=True)
        rev = (rec.get("review") or {}).get("output")
        dia_out = (rec.get("diagnosis") or {}).get("output")
        if rev:
            st.markdown(review_markdown(bid, rev, cost))
            ch = check_review(bid, rev)
            check_table(ch["citations"])
            for x in ch["unsupported_numbers"]:
                st.error(f"Figure not from the costing engine or the bill: {x}")
            for x in ch["governance_flags"]:
                st.error(f"Governance rule: {x}")
        else:
            st.info(f"{AGENT3} has not drafted a review for this bill yet.")
        free_route(f"p3review_{bid}", lambda: build_review_messages(bid, research_out, dia_out)[:2],
                   lambda out: store.save(bid, "review", {"output": out, "checks": check_review(bid, out)}, f"{AGENT3} review (free route)"))
        rt = (rec.get("redteam") or {}).get("output")
        st.subheader("Red-teamer")
        if rt:
            st.write("Recommendation:", f"**{rt.get('release_recommendation', '')}**")
            st.dataframe(pd.DataFrame(rt.get("issues", [])), use_container_width=True, hide_index=True)
        elif rev:
            if st.button("Run red-teamer", disabled=not live):
                from agents.appraisal import run_redteam
                store.save(bid, "redteam", {"output": run_redteam(bid, rev)["redteam"]}, "Red-team run")
                st.rerun()
        if rev:
            free_route(f"p3rt_{bid}", lambda: build_redteam_messages(bid, rev),
                       lambda out: store.save(bid, "redteam", {"output": out}, "Red-team (free route)"))
            st.subheader("Reviewer approval")
            edited = st.text_area("Edit the review (JSON) before approving", json.dumps(rev, indent=1, ensure_ascii=False), height=220)
            if st.checkbox("I have verified this review against the sources and approve it as the basis for a memo"):
                if st.button("Approve review"):
                    store.save(bid, "approved_review", json.loads(edited), "Reviewer approved the review")
                    store.set_status(bid, "review approved")
                    st.rerun()

    with t4:
        from agents.report import markdown as rep_md, docx_bytes
        rev = (rec.get("review") or {}).get("output") or {}
        comments = rec.get("comments") or [dict(c, include=True) for c in rev.get("preliminary_comments", [])]
        st.subheader("Preliminary comments")
        st.caption(f"Draft comments from {AGENT3}. Edit the wording, untick to drop, or add rows. Saved comments go into the report and the memo.")
        if comments:
            cdf = pd.DataFrame(comments)
            ed = st.data_editor(cdf[[c for c in ("include", "comment", "section", "basis") if c in cdf]],
                                num_rows="dynamic", use_container_width=True, key=f"ed_{bid}")
            if st.button("Save comments"):
                store.save(bid, "comments", ed.fillna("").to_dict("records"), "Reviewer edited comments")
                st.rerun()
        else:
            st.info(f"Run {AGENT3} (tab 3) to generate preliminary comments.")
        st.subheader("Preliminary report")
        md = rep_md(bid)
        d1, d2 = st.columns(2)
        d1.download_button("Download report (Word)", docx_bytes(bid), file_name=f"ActCheck_preliminary_report_{bid}.docx")
        d2.download_button("Download report (Markdown)", md, file_name=f"ActCheck_preliminary_report_{bid}.md")
        with st.expander("Preview"):
            st.markdown(md)

    with t5:
        approved = rec.get("approved_review")
        if not approved:
            st.info("The memo is drafted only from a review you have approved (Appraisal tab).")
        else:
            approved = dict(approved, preliminary_comments=[c for c in (rec.get("comments") or approved.get("preliminary_comments", [])) if c.get("include", True)])
            bureau = st.text_area("Bureau inputs to include (optional, e.g. BMB / OPCCB comments)")
            if st.button("Draft memorandum to the Secretary", disabled=not live):
                from agents.appraisal import run_memo
                m = run_memo(bid, approved, bureau)
                store.save(bid, "memo", m["memo"], "Memo drafted")
                store.set_status(bid, "memo drafted")
                st.rerun()
            free_route(f"p3memo_{bid}", lambda: build_memo_messages(bid, approved, bureau),
                       lambda txt: (store.save(bid, "memo", txt, "Memo (free route)"), store.set_status(bid, "memo drafted")), json_reply=False)
            if rec.get("memo"):
                memo_text = st.text_area("Memorandum (replace the position placeholder with your decision before the letter)", rec["memo"], height=350)
                if memo_text != rec["memo"] and st.button("Save memo edits"):
                    store.save(bid, "memo", memo_text, "Reviewer edited memo")
                    st.rerun()
                for x in check_document(bid, memo_text, "memo")["governance_flags"]:
                    st.warning(x)
                st.download_button("Download memo", memo_text, file_name=f"Memo_draft_{bid}.txt")
                if POSITION_PLACEHOLDER in memo_text:
                    st.info("Decide the position in the memo (replace the placeholder) to unlock the letter.")
                else:
                    if st.button("Draft letter to the committee chair / principal author", disabled=not live):
                        from agents.appraisal import run_letter
                        store.save(bid, "letter", run_letter(bid, memo_text)["letter"], "Letter drafted")
                        store.set_status(bid, "letter drafted")
                        st.rerun()
                    free_route(f"p3letter_{bid}", lambda: build_letter_messages(bid, memo_text),
                               lambda txt: (store.save(bid, "letter", txt, "Letter (free route)"), store.set_status(bid, "letter drafted")), json_reply=False)
                if rec.get("letter"):
                    st.text_area("Letter draft", rec["letter"], height=300)
                    for x in check_document(bid, rec["letter"], "letter")["governance_flags"]:
                        st.warning(x)
                    st.download_button("Download letter", rec["letter"], file_name=f"Letter_draft_{bid}.txt")
    with st.expander("Activity trail"):
        st.dataframe(pd.DataFrame(rec.get("trail", [])), use_container_width=True, hide_index=True)


# ---------------- Ask ActCheck ----------------
elif page == "Ask ActCheck":
    bid = st.session_state.get("bill")
    if not bid or bid not in bills:
        ui.notice("No bill open", "Open a bill with full text from the <b>Home</b> or <b>Bills</b> page, then ask about it here.", "info")
        st.stop()
    ui.section(f"Ask about {bills[bid]['label']}",
               "Answers use only this bill's workspace (sections, facts, costing engine, saved agent outputs) and cite their sources.")
    hist = st.session_state.setdefault(f"chat_{bid}", [])
    for m in hist:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
            for c in m.get("cites", []):
                if not c["exists"]:
                    st.caption(f"⚠ citation not found in the corpus: {c['citation']}")
    q = st.chat_input("e.g. What does the bill say about funding? Which existing agencies overlap?", disabled=not live)
    if not live:
        st.info("Add an API key under Reviewer settings (top-left ›) to use the chat.")
    if q:
        from agents.chat import ask
        hist.append({"role": "user", "content": q})
        try:
            ans, cites, _ = ask(bid, hist[:-1], q)
        except Exception as e:
            ans, cites = f"Error: {e}", []
        hist.append({"role": "assistant", "content": ans, "cites": cites})
        st.rerun()


# ---------------- Library ----------------
elif page == "Library":
    ui.section("Document library", "Full texts in ActCheck: bills, committee reports and existing laws, split into sections.")
    lib = pd.DataFrame([{k: b.get(k) for k in ("id", "label", "congress", "family", "kind", "n_sections", "text_source", "title")}
                        for b in bills.values()])
    st.dataframe(lib, use_container_width=True, hide_index=True, height=320)
    pick_id = st.selectbox("Read a document", sorted(bills), format_func=lambda x: f"{x} · {bills[x]['title'][:100]}")
    for s in secs.get(pick_id, []):
        with st.expander(f"Sec. {s['no']}. {s['heading']}"):
            st.write(s["text"])
    fam = ROOT / "data" / "processed" / "entity_families.csv"
    if fam.exists():
        ui.section("Pilot scope: entity-creation bill families", "18th–20th Congress, auto-extracted from titles.")
        st.dataframe(pd.read_csv(fam), use_container_width=True, hide_index=True)


# ---------------- Run log ----------------
elif page == "Run log":
    ui.section("Run log", "Every agent run and daily check, for the portfolio's run log and AI-use disclosure.")
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
        ui.section("Daily checks")
        st.dataframe(pd.DataFrame(runs[::-1]), use_container_width=True, hide_index=True)
    vl = ROOT / "docs" / "VERSION_LOG.md"
    if vl.exists():
        with st.expander("Version log"):
            st.markdown(vl.read_text())


# ---------------- About ----------------
else:
    ui.section(f"About {APP_NAME}", APP_TAGLINE)
    st.markdown(f"""
**{APP_NAME}** is a student prototype for PP5538 Digital Technology and Public Policy. It is not an official government
website and is not operated by the House of Representatives, the Senate or the Department of Budget and Management.

**Scope.** {APP_NAME} lists every House and Senate bill it can read from public sources. The agents are being tested first on
the **pilot scope**: bills that create a new national government agency, across all sectors. Other bills with full text can be
reviewed experimentally; the costing engine applies only to new agencies.

**How it works.** A daily check reads the House documents server and the Senate website's bill listing for new filings and
downloads their text (OCR if scanned). For each bill, three agents prepare drafts for a budget reviewer:

1. **{AGENT1}** (Evidence & Research): legislative history, earlier and parallel versions in both chambers, existing laws touched.
2. **{AGENT2}** (Diagnosis & Design): the problem the bill addresses, substantial differences from a related measure, design options.
3. **{AGENT3}** (Appraisal & Governance): preliminary review, cost range from a rules-based costing engine, risks, preliminary
   comments, and, after the reviewer approves, a memo to the Secretary and a letter to the committee or author.
   A separate red-teamer checks the review first.

**Safeguards.** Every claim must cite and quote a source, and the portal checks those quotes automatically. Peso figures
may only come from the costing engine or the bill. Drafts never state a DBM position or carry officials' names or
signatures. The reviewer approves each step. Every output is labelled: *{LABEL}*

**Data and licences.** House and Senate bill documents (public); Open Congress Data (BetterGov.PH, CC0 1.0); Philippine Legal
Documents Library (BetterGov.PH from Lawphil, CC BY-NC 4.0); DBM NBC No. 601 salary schedule; COA annual audit reports.
The daily check follows each site's robots.txt, waits between requests and does not bypass bot protection. Senate content is
not used to train AI models. Internal DBM documents are not used.

**Limits.** Prototype for coursework. House bills before the daily check started are listed from Open Congress Data, which
has gaps; costing is order-of-magnitude; comparator and benefit figures must be confirmed; saved reviews on the hosted
portal reset when it restarts (download your reports).
""")

ui.footer(APP_NAME, LABEL)
