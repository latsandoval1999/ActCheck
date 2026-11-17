"""How it Works page: the agentic workflow, how it fits the DBM process in the Citizen's Charter, what each agent
does with its safeguards, and the safeguards and limits of the prototype."""
from html import escape

import streamlit as st

import ui
from icons import svg, _P
from urllib.parse import quote

CHARTER_PDF = "https://www.dbm.gov.ph/wp-content/uploads/AboutDBM/%5BFINAL-COPY%5D-Updated-DBM-Charter,-1st-Edition,-CY-2026.pdf"

# DBM Citizen's Charter CY 2026 (1st ed., March 2026), service 26 "Preparation of DBM Position Paper on Proposed
# Legislative Measures and Executive Issuances from Agencies": multistage, G2G, 20 steps, 39 working days.
# (stage, Charter steps, tasks, who, Charter days, ActCheck support, illustrative days with ActCheck)
STAGES = [
    ("Receive the request", "1", "Receive the letter of request and upload the complete documents to the Document Management System",
     "BILLS divisions (administrative staff)", 2,
     "The daily check has usually already found, read and typed the bill, so its text, type and history are ready on arrival.", 1),
    ("Refer to the bureaus", "2-7", "Prepare the referral memorandum; Chief reviews and endorses; Director reviews and signs; upload for the bureaus",
     "BILLS analysts, Chief, Director", 1,
     "TrAIce's evidence brief and the bill's type suggest which bureaus to ask and what to ask them.", 1),
    ("Bureau comments", "8-9", "Concerned bureaus (e.g. BMB, OPCCB) prepare and submit comments; BILLS receives and records them",
     "DBM bureaus, services and offices", 15,
     "Bureaus receive CompAIre's list of substantial differences and ApprAIsal's cost range with sources, so they comment on the points that matter.", 10),
    ("Prepare the position paper", "10-15", "Prepare the DBM position paper from the inputs; Chief and Director review, approve and sign; release the draft to the Legal and Legislative Group",
     "BILLS analysts, Chief, Director", 15,
     "The memorandum and letter are pre-filled in DBM format from the approved review; every finding cites a checked section.", 7),
    ("Legal and Legislative Group review", "16-17", "The Supervising Senior Official reviews, signs and endorses to the Office of the Secretary",
     "Supervising Senior Official, LL Group", 2,
     "Citations and the activity trail let reviewers check sources quickly; the review itself stays with them.", 2),
    ("Office of the Secretary", "18-19", "The Chief of Staff reviews and endorses; the Secretary approves the position paper",
     "Chief of Staff; Secretary", 3, "No change: approval stays with the Secretary.", 3),
    ("Release", "20", "Release the DBM position paper to the requesting party", "BILLS divisions", 1,
     "The letter is drafted from the approved memorandum, ready for release.", 1),
]


def p(text):
    ui.html(f'<div class="ac-out"><p>{text}</p></div>')


def timeline():
    total = sum(s[4] for s in STAGES)
    new = sum(s[6] for s in STAGES)
    colors = ["#0B2545", "#13315C", "#D4A72C", "#B8322A", "#5B6B85", "#7A869A", "#1E6B47"]

    def bar(key):
        return "".join(f'<div style="flex:{st_[key]} 0 0; background:{colors[i]}" title="{escape(st_[0])}: {st_[key]} working day{'s' if st_[key] != 1 else ''}">'
                       f'{st_[key]}</div>' for i, st_ in enumerate(STAGES))
    legend = "".join(f'<span><i style="background:{colors[i]}"></i>{escape(st_[0])}</span>' for i, st_ in enumerate(STAGES))
    ui.html(f'''<div class="ac-tl">
<div class="ac-tl-row"><div class="ac-tl-lab"><b>Charter today</b><span>{total} working days</span></div>
  <div class="ac-tl-bar" style="width:100%">{bar(4)}</div></div>
<div class="ac-tl-row"><div class="ac-tl-lab"><b>With ActCheck</b><span>about {new} working days (illustrative)</span></div>
  <div class="ac-tl-bar" style="width:{100 * new / total:.1f}%">{bar(6)}</div></div>
<div class="ac-legend" style="margin-top:.6rem">{legend}</div></div>''')
    return total, new


def agent_card(ico, kicker, name, does, guards, output, wide=False, dark=False):
    li = lambda xs: "".join(f"<li>{x}</li>" for x in xs)  # noqa: E731
    return (f'<div class="ac-acard{" wide" if wide else ""}{" dark" if dark else ""}"><div class="ac-ahead"><span class="ac-aico">{svg(ico, 28)}</span>'
            f'<div><div class="ac-fk">{escape(kicker)}</div><div class="ac-aname">{escape(name)}</div></div></div>'
            f'<div class="ac-acols"><div><div class="ac-asub">What it does</div><ul>{li(does)}</ul></div>'
            f'<div><div class="ac-asub">{svg("shield", 13, stroke=2.2)} Safeguards</div><ul>{li(guards)}</ul></div></div>'
            f'<div class="ac-fout"><div class="lab">{svg("files", 13, stroke=2.2)} Output</div><div class="val">{escape(output)}</div></div></div>')


def render(a1, a2, a3, workflow):
    ui.section("How it Works", "From a newly filed bill to DBM comments for legislators",
               "ActCheck is an agentic AI system: a daily check plus three agents that each do one part of a preliminary legislative review, "
               "with the analyst checking and approving every step. Nothing leaves ActCheck as a DBM position unless the analyst writes it.")
    ui.flow2(workflow)

    ui.section("The current process", "Where ActCheck fits in the DBM Citizen's Charter",
               f'The DBM Citizen\'s Charter <a href="{CHARTER_PDF}" target="_blank">CY 2026 (1st edition, March 2026)</a> sets out the service '
               '"Preparation of DBM Position Paper on Proposed Legislative Measures and Executive Issuances from Agencies" as a multistage, '
               'government-to-government service of 20 steps with a total processing time of <b>39 working days</b>. (The DBM service web page '
               'shows an earlier total of 32 working days.) ActCheck does not change who decides or signs; it prepares the evidence and drafts '
               'each stage needs, which could shorten the stages that depend on gathering and writing.')
    total, new = timeline()
    rows = []
    for name, steps, tasks, who, d0, helps, d1 in STAGES:
        saved = d0 - d1
        rows.append([f"<b>{escape(name)}</b><br><span style='color:var(--mute);font-size:.78rem'>Steps {steps} · {escape(who)}</span>",
                     escape(tasks), f"{d0}", escape(helps),
                     f"<b>{d1}</b>" + (f' <span class="ac-badge green">−{saved}</span>' if saved else "")])
    rows.append(["<b>Total</b>", "", f"<b>{total}</b>", "", f"<b>{new}</b> <span class='ac-badge green'>−{total - new}</span>"])
    ui.table(["Stage", "Tasks in the Charter", "Charter (working days)", "How ActCheck helps", "With ActCheck (illustrative)"], rows, mono_cols=(2, 4))
    ui.note(f"<b>Potential reduction: about {total - new} working days ({(total - new) / total:.0%}).</b> The largest savings are in preparing the "
            "position paper (drafts pre-filled from an approved, cited review) and in bureau comments (bureaus start from the key differences and a "
            "sourced cost range instead of the full text). These figures are illustrative targets, not measured results; a time-and-motion pilot "
            "with BILLS analysts would be needed to confirm them. Review and approval times are left unchanged on purpose.")
    st.caption("Source: DBM Citizen's Charter CY 2026, 1st edition (March 2026), service 26. Steps 10-15 list no separate time; their 15 days are "
               "the remainder of the 39-day total.")

    ui.section("The agents", "What each one does, and its safeguards",
               "Each agent does one part of the review and hands its output to the next. Every finding must point to its source, and every "
               "step ends with the analyst's checklist.")
    cards = [
        agent_card("daily", "Every morning · 9:00 AM", "Daily check",
                   ["Checks the House documents server for new bill numbers and catches up older bills missing from the list",
                    "Reads each new bill, including scanned pages (text recognition)",
                    "Classifies each bill: scope of application (general or public, local application, private or named grantee) and one of "
                    "18 content categories, from rules on its title",
                    "Flags bills that Article VI, Section 24 of the Constitution requires to originate in the House, and bills related to the "
                    "44 LEDAC Common Legislative Agenda measures of the 20th Congress",
                    "Checks every data source and records the result in the Run log"],
                   ["Follows each website's rules for automated visitors and never bypasses access protections",
                    "A failed source is reported as 'source unavailable', never as 'no new bills'",
                    "Types are a first pass: about 5% stay 'Other or unclassified' and the analyst confirms the type",
                    "Senate content is not used to train AI models"],
                   "New bills on the Bills page, typed and flagged", dark=True),
        agent_card("trace", "Step 1 · Evidence and Research", f"{a1} · Trace the bill",
                   ["Explains what the bill proposes and how it fits the FY 2027 Budget Priorities Framework and the LEDAC agenda",
                    "Traces its history and groups related bills: filed in a past Congress, filed again, merged, the other chamber's version, "
                    "or an alternative proposal",
                    "Lists the laws the bill amends, overlaps or refers to, and its funding provisions",
                    "Drafts memo Parts II (Salient Features) and III (Related Measures and Policy Considerations)",
                    "In the checklist, notes what is established (verified in a full text) and what is contested or not shown in the data"],
                   ["Every related bill or law is backed by a passage from the cited section; ActCheck checks it word for word, figures included",
                    "Each related bill shows its source: full text, scanned text or title only",
                    "A bill not in the records is reported as not found, never guessed; instructions written inside a bill are ignored",
                    "Each output gets an evidence grade, A (strong) to D (weak), set by ActCheck, not by the agent"],
                   "Memo Parts II and III"),
        agent_card("compare", "Step 2 · Diagnosis and Design", f"{a2} · Spot the changes",
                   ["States the problem the bill addresses",
                    "Compares each major provision with the related bill that offers a real alternative, not a copy",
                    "Recommends one of four options for each: retain, adapt the alternative, adapt it with revisions, or remove, with trade-offs",
                    "Drafts memo Part IV (Comments and Recommendations) for the provisions that need a decision",
                    "Argues against its own recommendations and states the bill's theory of change; both appear in the checklist"],
                   ["Every comparison cites both sections, and ActCheck checks each passage",
                    "ActCheck flags a self-critique that looks too easy on its own recommendations",
                    "Possible duplication and cost effects go to ApprAIsal; CompAIre never states the DBM position",
                    "Each output gets an evidence grade, A to D, set by ActCheck"],
                   "Memo Part IV"),
        agent_card("appraise", "Step 3 · Appraisal and Governance", f"{a3} · Weigh the impact",
                   ["Leads a team of sub-agents: Costing (Personnel Services, MOOE and Capital Outlay from DBM costing rules and the 2026 "
                    "salary schedule), Duplication (overlap with existing agencies under RA No. 12231), Referral (the DBM bureaus that cover "
                    "the agencies named in the bill) and Recommendation (one of three Part VII options)",
                    "Drafts memo Parts V (Fiscal and Budgetary Requirements), VI (Possible Duplication) and VII (Recommendation)",
                    "A Red-teamer sub-agent checks every output for scope, figures, consistency between parts and missing bureaus; its verdict "
                    "appears in the checklist"],
                   ["Every peso figure comes from the cost calculator or the bill; any other figure is rejected",
                    "An output is rejected if it states a DBM position outside Part VII, names or signs for an official, gives political advice, "
                    "or includes personal contact details",
                    "The analyst confirms the recommendation in Step 4; drafts carry the AI-assisted label",
                    "Each output gets an evidence grade, A to D, set by ActCheck"],
                   "Memo Parts V to VII; bureaus to consult", wide=True),
        agent_card("billy", "Companion", "BILLy · Ask about the bill or the site",
                   ["With a bill open in the workspace, answers questions about that bill from its sections, the cost estimate and the agents' findings",
                    "With no bill open, answers questions about ActCheck: the agents, data sources, Library, Run log, safeguards"],
                   ["Every citation in an answer is checked", "When live runs are off, it quotes the matching passages of the bill"],
                   "Answers with section references"),
        agent_card("analyst", "The analyst", "Human checkpoints",
                   ["Each step ends with a checklist and a notes box; the next step stays locked until every item is ticked",
                    "Edits any output, records the bureaus' comments, confirms the recommendation and downloads the memo and letter"],
                   ["Every action is recorded in the activity trail", "Problem reports are kept with the bill and in the Run log"],
                   "Decisions the analyst owns", dark=True),
    ]
    tiles = [("daily", "Every morning", "Daily check"), ("trace", "Step 1", a1), ("compare", "Step 2", a2), ("appraise", "Step 3", a3),
             ("billy", "Companion", "BILLy"), ("analyst", "The analyst", "Checkpoints")]
    css = []
    for i, (ico, _, _) in enumerate(tiles, 1):
        uri = quote(f"<svg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 24 24' fill='none' stroke='#0B2545' stroke-width='1.8' "
                    f"stroke-linecap='round' stroke-linejoin='round'>{_P[ico]}</svg>")
        css.append(f'.st-key-agent_tile div[role="radiogroup"] > div:nth-child({i}) label::before{{background-image:url("data:image/svg+xml,{uri}");}}')
    ui.html("<style>" + "".join(css) + "</style>")
    st.caption("Click a step to see what it does, its safeguards and its output.")
    names = [f"{k} · {n}" for _, k, n in tiles]
    pick = st.radio("Step", names, key="agent_tile", horizontal=True, label_visibility="collapsed")
    ui.html('<div class="ac-agrid one">' + cards[names.index(pick)] + "</div>")

    ui.section("Safeguards and Limits", "What ActCheck does to stay trustworthy, and what to keep in mind",
               "ActCheck is a prototype for coursework. It is tested first on bills that create a national government agency; other bills "
               "can be reviewed, but the cost estimate is designed for new agencies. Bill types come from the titles and are approximate. Some "
               "older House bills come from Open Congress Data, which has gaps that the daily check is filling. Review progress and public "
               "reports are saved to a Google Sheet, so they are kept when the site restarts; attached files in checklists are not. Every output "
               "is labelled an AI-assisted preliminary draft for DBM reviewer validation, not an official position.")
    from agents import grading
    ui.html("<p style='margin:.9rem 0 .2rem'><b>Evidence grade of each agent output</b></p>")
    ui.html("<ul style='margin:.2rem 0 .6rem 1.1rem;font-size:.92rem;line-height:1.5'>" + "".join(f"<li>{x}</li>" for x in grading.METHOD) + "</ul>")
    ui.table(["Grade", "Points (of 8)", "Meaning for the reviewer"], [
        ["A · Strong", "7–8", "Findings rest on the official text, every cited passage verified; confirm the few points noted."],
        ["B · Moderate", "5–6", "Usable; verify the items under 'To note' against the House or Senate record or the bill PDF before ticking."],
        ["C · Limited", "3–4", "Treat as a lead only; check the main findings against the sources."],
        ["D · Weak", "0–2", "Do not rely on it; redo the step from the sources."]])
    ui.html("<p style='margin:.9rem 0 .2rem'><b>Responsible AI: how ActCheck follows the government's AI principles</b></p>")
    p("DICT-CSC Joint Memorandum Circular No. 003, s. 2026 sets the principles for the ethical and responsible development, deployment and use "
      "of AI in government; NPC Advisory No. 2024-04 applies the Data Privacy Act to AI systems. The table shows how the prototype meets each "
      "principle and what an agency would still need to do before real use.")
    ui.table(["Principle (JMC 003, Sec. 5-10)", "How ActCheck meets it", "Still needed before agency use"], [
        ["Proportionality and do no harm", "Used only for preliminary review within DBM-BILLS' existing mandate; agents never set a position or sign.",
         "A risk assessment by the deploying office."],
        ["Human-centricity; final decision by a human", "Checklists lock each step until the analyst approves; only the analyst confirms the recommendation; every action is in the activity trail.",
         "User testing with BILLS analysts; consult staff whose work changes."],
        ["Fairness and non-discrimination", "No personal data is used to judge anyone; the agent may not describe legislators' motives; reviewers can flag biased wording.",
         "A bias check across bill types and chambers (coverage gaps in House listings, title-based types)."],
        ["Transparency and explainability", "Each finding is backed by a checked passage from its source; outputs say who prepared them; this page explains inputs, limits and outputs.",
         "Publish the disclosure in the agency's own AI policy."],
        ["Data governance, privacy and protection", "Only public documents (bills, laws, budget and audit reports); the only personal data are legislators' names as published.",
         "Privacy impact assessment; classify data under Sec. 9 before adding internal files."],
        ["Responsibility and accountability", "Every output is labelled an AI-assisted preliminary draft; the analyst who approves is accountable; runs and approvals are logged.",
         "Name the accountable unit; the internal AI committee (IT and Legal) under Sec. 8 reviews use."],
        ["Reporting and feedback (Sec. 6b)", "Each checklist ends with a Notes and attachments box for corrections, and members of the public can send reports from the Bills page; both are kept with the bill.",
         "Route reports to the system owner and fix within a set time."],
        ["Disclosure of AI use (Sec. 6b)", "Reports, memos and letters carry the AI-assisted label; the Run log shows which agent prepared what, and when.",
         "Agency rule on how AI use is disclosed to Congress."],
        ["Cyber safety and security", "No keys or passwords stored in the code; only public data on the hosted prototype.",
         "Vulnerability assessment and access control before internal deployment."],
        ["Robustness and reliability", "Sources documented; automatic checks on citations, peso figures and scope; a Red-teamer on every ApprAIsal output; tests run on every change.",
         "Regular monitoring of accuracy on new bills (Sec. 10)."],
        ["Sustainability", "ActCheck prepares a draft first at no cost; Claude's outputs are saved and reused, not regenerated.",
         "Track usage and cost per review."],
    ])
    st.caption("Sources: DICT-CSC JMC No. 003, s. 2026; NPC Advisory No. 2024-04; RA 10173 (Data Privacy Act of 2012).")
