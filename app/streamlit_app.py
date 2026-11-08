"""Reviewer portal for preliminary review of bills that create a government entity.

    streamlit run app/streamlit_app.py

Pages: Inbox (new measures found by the daily watcher + every bill in the corpus) ->
Bill workspace (one-click full review; Evidence, Comparison, Appraisal, Comments & report,
Memo & letter) -> Ask about this bill (grounded chat) -> Library -> Run log -> About.

Without an API key every rules-only part works, and each agent can be run through the free
route: download its prompt, run it in a Claude chat, paste the reply back to check and save it.
"""
import json
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agents import llm, store  # noqa: E402
from pipeline.compare import load, related_bills  # noqa: E402

from agents.names import APP_NAME, APP_TAGLINE, AGENT1, AGENT2, AGENT3  # noqa: E402
LABEL = "AI-assisted preliminary draft for DBM reviewer validation. Not an official position."
st.set_page_config(page_title=APP_NAME, page_icon="📜", layout="wide")
bills, secs = load()
PAGES = ["Inbox", "Bill workspace", "Ask about this bill", "Library", "Run log", "About & governance"]


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


def pick(df, key):
    """Single-row selection from a dataframe; returns the row index or None."""
    ev = st.dataframe(df, use_container_width=True, hide_index=True, on_select="rerun", selection_mode="single-row", key=key)
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


def reviewable():
    return sorted([b for b in bills.values() if b["chamber"] in ("HB", "SB")],
                  key=lambda b: (-(int(b["congress"] or 0)), b["chamber"], int(b["id"].split("-")[2])))


def inbox_items():
    p = ROOT / "data" / "watch" / "inbox.json"
    return json.loads(p.read_text()) if p.exists() else []


def pick_reference(bid, research_out):
    order = ("consolidated", "counterpart", "near-copy", "earlier version", "competing")
    if research_out:
        for lab in order:
            for r in research_out.get("related", []):
                if lab in (r.get("relationship") or "") and r.get("id") in bills and r["id"] != bid:
                    return r["id"]
    rel = related_bills(bid, top=1)
    return rel[0]["id"] if rel else None


# ---------------- sidebar ----------------
if "_goto" in st.session_state:  # apply navigation requested on the previous run
    st.session_state["nav"] = st.session_state.pop("_goto")
    for k in ("inbox_tbl", "corpus_tbl"):  # clear table selections so they don't re-trigger
        st.session_state.pop(k, None)
st.session_state.setdefault("nav", "Inbox")
with st.sidebar:
    st.title(APP_NAME)
    st.caption(f"{APP_TAGLINE}. Preliminary review of proposed measures that create a government entity. Student prototype (PP5538), not an official DBM system.")
    page = st.radio("Go to", PAGES, key="nav")
    if st.session_state.get("bill"):
        b = bills.get(st.session_state["bill"])
        if b:
            st.info(f"Open bill: **{b['label']}** ({b['congress']}th)\n\nStatus: {store.load(b['id']).get('status', 'new')}")
    pasted = st.text_input("Anthropic API key (optional, this session only)", type="password")
    if pasted:
        st.session_state["user_api_key"] = pasted
    live = bool(llm.api_key())
    st.write("AI agents:", "**on**" if live else "**off** (rules-only + free route)")
    st.warning(LABEL)


# ---------------- Inbox ----------------
if page == "Inbox":
    st.header("Inbox")
    inbox = inbox_items()
    statuses = store.all_status()
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("New measures (watcher)", sum(1 for x in inbox if x["status"] in ("new", "triaged")))
    c2.metric("Bills in the corpus", sum(1 for b in bills.values() if b["chamber"] in ("HB", "SB")))
    c3.metric("Reviews in progress", sum(1 for s in statuses.values() if s in ("in review", "review approved")))
    c4.metric("Memos / letters drafted", sum(1 for s in statuses.values() if s in ("memo drafted", "letter drafted")))
    sp = ROOT / "data" / "watch" / "state.json"
    if sp.exists():
        runs = json.loads(sp.read_text()).get("runs", [])
        if runs:
            last = runs[-1]
            st.caption(f"Last daily check: {last['time']} UTC; new bills found: {last['found']}."
                       + (f" Problems: {last['errors']}" if last.get("errors") else ""))
    else:
        st.caption("The daily watcher has not run yet (it runs on GitHub every morning once the project is online).")

    st.subheader("New measures found by the daily check")
    if inbox:
        df = pd.DataFrame([{"Bill": x["id"], "Screen": x["screen"], "Status": statuses.get(x["id"], x["status"]),
                            "Title": x["title"][:160], "Found": x["found"][:10]} for x in inbox][::-1])
        only = st.checkbox("Show only bills that create a government entity", value=True)
        if only:
            df = df[df["Screen"] == "entity-creating"]
        i = pick(df.reset_index(drop=True), "inbox_tbl")
        if i is not None and df.iloc[i]["Bill"] in bills:
            go("Bill workspace", df.iloc[i]["Bill"])
    else:
        st.info("No new measures yet. Meanwhile, open any bill from the corpus below.")

    st.subheader("All bills in the corpus")
    q = st.text_input("Search by number or title", placeholder="e.g. water resources, HB 2322, fisheries")
    rows = []
    for b in reviewable():
        if q and q.lower().replace(" ", "") not in (b["label"] + b["title"] + b["family"]).lower().replace(" ", ""):
            continue
        rows.append({"Bill": b["id"], "Label": b["label"], "Congress": b["congress"], "Family": b["family"],
                     "Status": statuses.get(b["id"], "new"), "Title": b["title"][:150]})
    df2 = pd.DataFrame(rows)
    i = pick(df2, "corpus_tbl") if len(df2) else None
    if i is not None:
        go("Bill workspace", df2.iloc[i]["Bill"])


# ---------------- Bill workspace ----------------
elif page == "Bill workspace":
    bid = st.session_state.get("bill")
    if not bid or bid not in bills:
        st.info("Open a bill from the Inbox first.")
        st.stop()
    from agents.research import evidence_pack, brief_markdown, build_messages as p1_msgs, check_output as p1_check
    from agents.diagnosis import fact_diff, family_designs, report_markdown as p2_md, build_messages as p2_msgs, check_output as p2_check
    from agents.costing import cost_range, peso
    from agents.appraisal import (review_markdown, check_review, check_document, POSITION_PLACEHOLDER,
                                  build_review_messages, build_redteam_messages, build_memo_messages, build_letter_messages)
    b = bills[bid]
    rec = store.load(bid)
    st.header(f"{b['label']} · {b['congress']}th Congress")
    st.caption(b["title"])
    status = rec.get("status", "new")
    st.progress((store.STATUSES.index(status) + 1) / len(store.STATUSES), text=f"Status: {status}")
    st.caption(f"Family: {b['family']} · Text: {b['text_source']} ({b['n_sections']} sections)"
               + (" · OCR text: check quotes against the PDF" if b["text_source"] == "ocr" else ""))

    research_out = (rec.get("research") or {}).get("output")
    cand = [r["id"] for r in related_bills(bid, top=15)]
    default_ref = pick_reference(bid, research_out) or (cand[0] if cand else None)
    if default_ref and default_ref not in cand:
        cand = [default_ref] + cand
    ref = st.selectbox(f"Compare with ({AGENT2} reference)", cand, index=cand.index(rec.get("reference", default_ref)) if rec.get("reference", default_ref) in cand else 0,
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
        st.caption("AI agents are off: each tab shows the rules-only analysis and a free route to run the agent in a Claude chat.")

    t1, t2, t3, t4, t5 = st.tabs([f"1 · {AGENT1} (evidence)", f"2 · {AGENT2} (comparison)", f"3 · {AGENT3} (appraisal)", "Comments & report", "Memo & letter"])

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
            fd = fact_diff(bid, ref)
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
            ed = st.data_editor(pd.DataFrame(comments)[[c for c in ("include", "comment", "section", "basis") if c in pd.DataFrame(comments)]],
                                num_rows="dynamic", use_container_width=True, key=f"ed_{bid}")
            if st.button("Save comments"):
                store.save(bid, "comments", ed.fillna("").to_dict("records"), "Reviewer edited comments")
                st.rerun()
        else:
            st.info(f"Run {AGENT3} (tab 3) to generate preliminary comments.")
        st.subheader("Preliminary report")
        md = rep_md(bid)
        st.download_button("Download report (Word)", docx_bytes(bid), file_name=f"Preliminary_report_{bid}.docx")
        st.download_button("Download report (Markdown)", md, file_name=f"Preliminary_report_{bid}.md")
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
                ready = POSITION_PLACEHOLDER not in memo_text
                if not ready:
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


# ---------------- Ask about this bill ----------------
elif page == "Ask about this bill":
    bid = st.session_state.get("bill")
    if not bid or bid not in bills:
        st.info("Open a bill from the Inbox first.")
        st.stop()
    st.header(f"Ask about {bills[bid]['label']}")
    st.caption("Answers use only this bill's workspace (sections, facts, costing engine, saved agent outputs) and cite their sources.")
    hist = st.session_state.setdefault(f"chat_{bid}", [])
    for m in hist:
        with st.chat_message(m["role"]):
            st.markdown(m["content"])
            for c in m.get("cites", []):
                if not c["exists"]:
                    st.caption(f"⚠ citation not found in the corpus: {c['citation']}")
    q = st.chat_input("e.g. What does the bill say about funding? Which existing agencies overlap?", disabled=not live)
    if not live:
        st.info("Add an API key in the sidebar to use the chat.")
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
    st.header("Library")
    st.dataframe(pd.DataFrame([{k: b.get(k) for k in ("id", "label", "congress", "family", "kind", "n_sections", "text_source", "title")}
                               for b in bills.values()]), use_container_width=True, hide_index=True)
    pick_id = st.selectbox("Read a document", sorted(bills))
    for s in secs.get(pick_id, []):
        with st.expander(f"Sec. {s['no']}. {s['heading']}"):
            st.write(s["text"])
    fam = ROOT / "data" / "processed" / "entity_families.csv"
    if fam.exists():
        st.subheader("Entity-creation bill families, 18th–20th Congress (auto-extracted)")
        st.dataframe(pd.read_csv(fam), use_container_width=True, hide_index=True)


# ---------------- Run log ----------------
elif page == "Run log":
    st.header("Run log")
    log = ROOT / "logs" / "runs.jsonl"
    if log.exists():
        st.dataframe(pd.DataFrame([json.loads(x) for x in log.read_text().splitlines()]).drop(columns=["output"], errors="ignore"),
                     use_container_width=True, hide_index=True)
    else:
        st.caption("No API runs yet in this deployment.")
    sp = ROOT / "data" / "watch" / "state.json"
    if sp.exists():
        st.subheader("Daily watcher runs")
        st.dataframe(pd.DataFrame(json.loads(sp.read_text()).get("runs", [])), use_container_width=True, hide_index=True)
    vl = ROOT / "docs" / "VERSION_LOG.md"
    if vl.exists():
        with st.expander("Version log"):
            st.markdown(vl.read_text())


# ---------------- About ----------------
else:
    st.header("About & governance")
    st.markdown(f"""
**{APP_NAME}**: {APP_TAGLINE}. A student prototype for PP5538, not an official DBM system.

**What it does.** A daily watcher looks for newly filed House and Senate bills and screens for those that create a
government entity. For each bill, three agents prepare a preliminary review for a DBM reviewer:

1. **{AGENT1}** (Evidence & Research): legislative history, earlier and parallel versions in both chambers, existing laws touched.
2. **{AGENT2}** (Diagnosis & Design): the problem the bill addresses, substantial differences from a related measure, design options.
3. **{AGENT3}** (Appraisal & Governance): preliminary review, cost range from a rules-based costing engine, risks, preliminary
   comments, and, after the reviewer approves, a memo to the Secretary and a letter to the committee or author.
   A separate red-teamer checks the review first.

**Safeguards.** Every claim must cite and quote a source, and the portal checks those quotes automatically. Peso figures
may only come from the costing engine or the bill. Drafts never state a DBM position or carry officials' names or
signatures. The reviewer approves each step. Every output is labelled: *{LABEL}*

**Data.** House and Senate bill texts; Open Congress Data (BetterGov.PH, CC0); Philippine Legal Documents Library
(BetterGov.PH from Lawphil, CC BY-NC 4.0); DBM NBC No. 601 salary schedule; COA annual audit reports. OCR text is flagged.
Internal DBM documents are not used.

**Limits.** Prototype for coursework; costing is order-of-magnitude; comparator and benefit figures must be confirmed;
the Senate watcher route is untested; saved reviews on a hosted app reset when it restarts (download reports).
""")
