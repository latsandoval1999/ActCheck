"""How it Works page: the agentic workflow and how it fits the DBM-BILLS process in the Citizen's Charter."""
import streamlit as st

import ui

CHARTER = ("https://dbm.gov.ph/index.php/central-office/services-for-client-agencies/"
           "1597-preparation-of-dbm-position-paper-on-legislative-measures-and-proposed-executive-issuances-from-agencies")
CHARTER_PDF = "https://www.dbm.gov.ph/wp-content/uploads/AboutDBM/%5BFINAL-COPY%5D-Updated-DBM-Charter,-1st-Edition,-CY-2026.pdf"


def p(text):
    ui.html(f'<div class="ac-out"><p>{text}</p></div>')


def render(a1, a2, a3):
    ui.section("How it Works", "From a newly filed bill to DBM comments for legislators",
               "ActCheck is an agentic AI system: a daily check plus three agents that each do one part of a preliminary legislative "
               "review, with the analyst checking and approving every step. Nothing leaves ActCheck as a DBM position unless the analyst "
               "writes it.")

    ui.flow([("Every morning", "Daily check", "Reads new filings from the House documents server and the Senate bill listing; downloads "
              "and reads each bill (OCR if scanned) and classifies it.", "New bills on the Bills page", True),
             ("Step 1", f"{a1}", "Traces the bill's history in both chambers and the laws it touches.", "Legislative history", False),
             ("Step 2", f"{a2}", "Spots what changed against the closest related measure.", "Differences and options", False),
             ("Step 3", f"{a3}", "Weighs cost, risks and overlaps; drafts comments; red-team check.", "Preliminary review", False),
             ("The analyst", "Decide and send", "Approves each step, sets the position, finalizes memo and letter.", "DBM memo and letter", True)])

    ui.section("The current process", "What the DBM Citizen's Charter sets out",
               f'The Charter service <a href="{CHARTER}" target="_blank">"Preparation of DBM Position Paper on Legislative Measures and Proposed '
               'Executive Issuances from Agencies"</a> is classified as <b>complex</b> (government-to-government), available to the House, the '
               'Senate, the Presidential Legislative Liaison Office and agencies, with a stated total processing time of <b>32 working days</b> '
               'across 20 steps. ActCheck does not change who decides or signs; it prepares the evidence and drafts the analyst needs at each stage.')
    ui.table(["Stage in the Charter", "Charter time", "Who", "Where ActCheck helps"], [
        ["Receive the request and upload the documents", "2 working days", "BILLS divisions",
         "The daily check has usually already found and read the bill, so its history and text are ready before the request arrives."],
        ["Prepare and sign the referral memorandum to the concerned bureaus", "1 working day (Director review)", "BILLS analysts, Chief, Director",
         f"{a1}'s evidence brief and the bill's type (e.g. new agency, tax, local) suggest which bureaus to refer to and what to ask them."],
        ["Bureaus prepare and submit comments", "15 working days", "Concerned DBM bureaus (e.g. BMB, OPCCB)",
         f"Bureaus can be sent {a2}'s list of substantial differences and {a3}'s cost range with its assumptions, so they comment on the "
         "points that matter instead of starting from the full text."],
        ["Prepare the DBM position paper", "within the 32 days", "BILLS analysts",
         "The memorandum is pre-filled in DBM layout from the approved review and comments; the analyst completes offices, dates and position."],
        ["Review and sign through the chain (Chief, Director, Supervising Senior Official, Chief of Staff, Secretary)", "2 + 2 working days for the senior reviews", "BILLS and OSEC",
         "Every claim carries a section citation that was checked automatically, and the activity trail shows who approved each step."],
        ["Release the position paper", "1 working day", "BILLS divisions", "The letter to the committee chair or principal author is drafted from the approved memo."],
    ])
    st.caption("Source: DBM Citizen's Charter service page (step times as listed; some steps run in parallel). See also the "
               "Updated DBM Citizen's Charter, 1st Edition, CY 2026.")

    ui.section("The agents", "What each one does, and its safeguards")
    tabs = st.tabs([f"Daily check", f"1 · {a1}", f"2 · {a2}", f"3 · {a3}", "BILLy", "Human checkpoints"])
    with tabs[0]:
        p("<b>What it does.</b> Every day at 06:17 Manila time a scheduled job checks the House documents server for the next bill numbers and "
          "reads the Senate's public bill listing. New bills are downloaded and read (with OCR when the PDF is scanned), classified by type and "
          "scope, and listed on the Bills page. The full bill list is also refreshed from Open Congress Data.")
        p("<b>Safeguards.</b> It follows each site's robots.txt, waits between requests and never bypasses bot protection. A failed check is "
          "reported as 'source unavailable', never as 'no new bills'. Senate content is not used to train AI models.")
    with tabs[1]:
        p(f"<b>Purpose: trace the bill.</b> {a1} (the Evidence and Research Agent) builds the bill's legislative history: earlier versions in the "
          "18th and 19th Congress, its counterpart in the other chamber, refiled or consolidated copies, and the existing laws it amends or "
          "overlaps with.")
        p("<b>How.</b> A rules-only baseline first ranks candidate bills by text similarity and lists the laws the bill cites or resembles. "
          f"{a1} then reads the candidates and labels each relationship (earlier version, counterpart, near-copy, competing, precedent).")
        p("<b>Output and safeguards.</b> Each link must cite a section and quote it; ActCheck checks every quote against the source text and marks "
          "any it cannot find. Gaps the agent could not close are listed rather than guessed.")
    with tabs[2]:
        p(f"<b>Purpose: spot the changes.</b> {a2} (the Policy Diagnosis and Design Agent) compares the bill with the closest related measure "
          "(usually the counterpart or earlier version) section by section.")
        p("<b>Output.</b> The problem the bill says it addresses; a list of substantial differences (mandate, structure, positions and salary "
          "grades, funding, duration) with their likely cost effect; design options seen across related bills; and corrections to the "
          "rules-only section alignment.")
        p("<b>Safeguards.</b> Both versions are quoted for every difference; the non-AI alignment is shown beside the agent's so the analyst "
          "can see where they disagree.")
    with tabs[3]:
        p(f"<b>Purpose: weigh the impact.</b> {a3} (the Policy Appraisal and Governance Agent) drafts the preliminary review: summary, history, "
          "differences, overlaps with existing agencies, fiscal implications, risks, a verification checklist and preliminary comments.")
        p("<b>Costing.</b> The AI never does arithmetic. A rules-based costing engine computes a first-year range from the 2026 salary schedule "
          "(NBC No. 601), mandatory benefits and comparator agencies' audited expenses (COA reports); the agent may only quote those figures "
          "and the amounts stated in the bill. Any other peso figure is flagged.")
        p("<b>Red-teamer.</b> A second, independent agent reviews the draft for factual slips, unsupported claims and overstated status, and "
          "recommends whether it is ready for the analyst.")
        p("<b>Memo and letter.</b> After approval, the memorandum for the Secretary and the letter to the committee chair or principal author "
          "are drafted in DBM layout. They never include officials' names, signatures, approval boxes or a position: the analyst sets the "
          "position, and the letter unlocks only then.")
    with tabs[4]:
        p("<b>BILLy, the review companion.</b> The floating 'Ask Billy' button opens a chat about the bill that is open. With an API key, BILLy "
          "answers only from the bill's workspace (its sections, the costing engine, saved agent outputs) and every citation is checked. "
          "Without a key, BILLy works in search mode: it quotes the sections of the bill that best match the question.")
    with tabs[5]:
        p("<b>The analyst stays in charge.</b> Each step ends with a checklist (with space for notes and attached files). The next step stays "
          "locked until every item is ticked. Step 3 ends with the analyst's approval of the review; the memo is drafted only from an approved "
          "review, and the letter only after the analyst sets the position. Every action is recorded in the activity trail.")

    ui.section("Bill types", "How ActCheck classifies bills",
               "Each bill gets a scope of application (general or public, local application, or private or named grantee) and one primary "
               "content category (18 categories, from appropriations and taxation to commemorations and emergency response). Classification "
               "uses rules on the bill's title, so it is a first pass for browsing and charts; the analyst confirms the type during review. "
               "Bills that Article VI, Section 24 of the 1987 Constitution requires to originate in the House are flagged.")

    ui.section("Limits", "What to keep in mind")
    p("ActCheck is a prototype for coursework. The agents are tested first on bills that create a national government agency; other types can "
      "be reviewed, but the costing engine applies only to new agencies. House bills filed before the daily check began are listed from Open "
      "Congress Data, which has gaps. Reviews saved on the hosted portal reset when it restarts, so download reports, memos and letters. "
      "Every output is labelled as an AI-assisted preliminary draft for DBM reviewer validation, not an official position.")
