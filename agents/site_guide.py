"""What BILLy knows about ActCheck itself, for questions asked when no bill is open (Overview, How it Works and
the other pages). Search mode ranks these entries; AI mode answers from them only."""
import re

GUIDE = [
    ("What is ActCheck?", "ActCheck is an Agentic AI System for Philippine Legislative Review. It helps government analysts, first of "
     "all those who prepare the Department of Budget and Management's comments on bills, to trace a bill's history, see what changed "
     "from related measures, and assess its legal and budget implications, so they can give legislators timely, well-sourced comments. "
     "Three AI agents do the groundwork: TrAIce traces the bill, CompAIre spots the changes and ApprAIsal weighs the impact. The "
     "analyst checks and approves every step and alone decides the DBM position. Every finding cites the bill or law it comes from, "
     "and every output is an AI-assisted preliminary draft for reviewer validation. ActCheck is a student prototype for PP5538 "
     "(Lee Kuan Yew School of Public Policy), not an official government website."),
    ("What can BILLy do?", "BILLy is ActCheck's guide. On any page it answers questions about the portal: the agents, the data sources, "
     "the cost estimate, the Library and the Run log. When a bill is open in the Review workspace, BILLy answers questions about that "
     "bill from its own sections and the agents' findings, and points to the section it used."),
    ("What problem does it address?", "DBM must comment on a large volume of bills. The DBM Citizen's Charter (CY 2026) gives 39 working "
     "days and 20 steps for a position paper. The evidence for each review is scattered across two chamber websites, three Congresses, "
     "refiled and substitute versions, existing laws and budget data, and bills that create agencies often state no cost."),
    ("Which bills are covered?", "The Bills page lists every House and Senate bill of the 18th to 20th Congress from public sources. The "
     "agents are tested first on bills that create a national government agency, in any sector; other bills with full text can be "
     "reviewed, but the cost estimate applies only to new agencies."),
    ('What are the three agents?', 'TrAIce traces the bill: earlier versions, the counterpart in the other chamber, refiled copies and the laws it touches (memo Parts II and III). CompAIre spots the changes: it compares each major provision with the related bill that offers a real alternative, recommends what to keep or change, and argues against its own recommendations (Part IV). ApprAIsal weighs the impact: it leads a small team (Costing, Duplication, Referral and Recommendation) that estimates the cost, checks for overlap with existing agencies, proposes a recommendation and lists the DBM bureaus to consult (Parts V to VII). A Red-teamer checks every ApprAIsal draft.'),
    ('What does TrAIce do?', 'TrAIce (Evidence and Research) finds the related bills and laws and labels how each relates: filed in a past Congress, filed again this Congress, merged into this bill, Senate or House version, or an alternative proposal. Every link is backed by a passage from the cited section, which ActCheck checks word for word. Its checklist shows what is established, what is contested (for example, scanned or title-only sources) and what the data cannot establish.'),
    ('What does CompAIre do?', "CompAIre (Diagnosis and Design) states the problem the bill addresses and compares each major provision with the related bill that offers a real alternative. For each it recommends: retain the provision, adapt the alternative, adapt it with revisions, or remove the provision, with the trade-offs. It then argues against its own recommendations and states the bill's theory of change; both appear in its checklist. It drafts memo Part IV."),
    ('What does ApprAIsal do?', 'ApprAIsal (Appraisal and Governance) is a lead agent with four helpers: Costing estimates the cost of a new office; Duplication checks overlap with existing agencies under RA No. 12231; Referral lists the DBM bureaus to consult; Recommendation proposes one of three options for Part VII. A Red-teamer checks every draft for scope, figures and consistency, and its findings appear in the Step 3 checklist. ApprAIsal drafts memo Parts V to VII; the analyst confirms the recommendation.'),
    ('How is the cost estimated?', 'A fixed calculator, not the agent, estimates the first-year cost of a new office: Personnel Services from the 2026 salary schedule (NBC No. 601) with benefits, operating costs (MOOE) and equipment (Capital Outlay) from DBM costing parameters. Similar agencies in the FY 2026 budget and COA audit reports are cross-checks. The agent may only quote these figures. For bills that create a program rather than an office, the estimate does not apply.'),
    ("What is the daily check?", "Every day at 9:00 AM Manila time a scheduled job checks the data sources, looks for new House bills on the "
     "House documents server, reads them (including scanned pages), sorts them by type and lists them on the Bills page. It also "
     "catches up older House bills missing from the list. The Senate listing blocks GitHub's servers, so it is refreshed separately."),
    ("Where does the data come from?", "House bill PDFs from the House documents server; the Senate's public bill listing; Open Congress Data "
     "and the Philippine Legal Documents Library (BetterGov.PH); the FY 2026 GAA, DBM Staffing Summary and NBC No. 601; COA audit "
     "reports; the LEDAC Common Legislative Agenda; the DBM 2027 Budget Priorities Framework; and the PSA inflation report."),
    ("What is the Library?", "The Library has two parts. Review References lists the documents ActCheck relies on (budget, audit, policy, "
     "governance and legal references) with their date, purpose and a link. Full Text of Bills holds the bills, committee reports and "
     "laws ActCheck has read, divided into sections so every finding can point to an exact provision."),
    ('What is the Run log?', "The Run log shows the public reports sent from the Bills page (reviewers can open each one), whether the Google Sheet that keeps reports and review progress is connected, the data sources and when they were last checked, the agent outputs prepared by Claude for each bill with their grades and the Red-teamer's verdict, and the project log."),
    ("What are bill types?", "Each bill gets a scope (general or public, local application, or private or named grantee) and one of 18 "
     "content categories from rules on its title. 'Other or unclassified' holds titles no rule matches, such as bills on sports, "
     "culture, or science that use none of the key words; the analyst confirms the type during review."),
    ("What is the LEDAC flag?", "Bills related by title to the 44 Common Legislative Agenda measures identified by the LEDAC on 30 September "
     "2025 are flagged 'LEDAC priority' on the Bills page; the analyst confirms the match."),
    ("How do I review a bill?", "Click 'Reviewer Log In' at the top right (or Log In on any bill), open the Bills page, click Review on a bill, then work through "
     "the four steps in the Review workspace. Each step ends with a checklist that unlocks the next one."),
    ("How can the public share inputs on a bill?", "On the Bills page, click Report on any bill. The bill's number and title are filled in; "
     "choose the part of the review it concerns (TrAIce: legislative history; CompAIre: comparison and policy design; ApprAIsal: cost, overlap or duplication, implementation or governance risk; or Others) and the topic, write a message "
     "and attach files if you like. Name, email and contact number are optional and seen only by reviewers. Reports are kept in a "
     "Google Sheet so they survive restarts, and reviewers see a clickable notice in the part of the Review workspace each report concerns."),
    ('Who decides the DBM position?', 'Only the analyst. The agents prepare evidence and drafts; ApprAIsal proposes one of three recommendations, and the analyst confirms or changes it in Step 4. The letter follows the confirmed recommendation.'),
    ('What are the safeguards?', 'Every link to a bill or law is backed by a passage that ActCheck checks word for word; peso figures must come from the calculator or the bill; drafts may not state a DBM position, name or sign for officials, give political advice or include personal details; a Red-teamer checks every ApprAIsal draft; checklists lock each step until the analyst approves; everything is logged. ActCheck follows DICT-CSC Joint Memorandum Circular No. 003, s. 2026 on responsible AI in government.'),
    ('What are the limits?', 'It is a prototype: the agents are tested first on bills that create agencies; bill types come from the titles; the cost range is an order of magnitude; House lists have gaps that the daily catch-up is filling; the Senate list is refreshed separately. Review progress and public reports are kept in a Google Sheet; files attached to checklists are not.'),
    ('Does it need an AI key?', "No. Outputs prepared by TrAIce, CompAIre and ApprAIsal (Claude) are saved with ActCheck and shown automatically; bills without them show ActCheck's draft. With an Anthropic key, reviewers can also run the agents on the site."),
]

STOP = set("the and for that this with what how does who are its is can you about actcheck".split())


def _tok(s):
    return [w[:6] for w in re.findall(r"[a-z]{3,}", s.lower()) if w not in STOP]


# The longer FAQ (data/reference/billy_faq.json) is added to the guide: public use, reviewer use, the agents, the
# cost estimate, bills and status, data and updates, the Library and Run log, safeguards and BILLy itself.
def _faq():
    import json
    from pathlib import Path
    p = Path(__file__).resolve().parents[1] / "data" / "reference" / "billy_faq.json"
    try:
        return [(x["q"], x["a"]) for x in json.loads(p.read_text())]
    except Exception:
        return []


_seen = {q for q, _ in GUIDE}
GUIDE += [(q, a_) for q, a_ in _faq() if q not in _seen]

# questions that mean "what is this site?" (the word ActCheck itself is too common in the guide to rank on)
ABOUT = re.compile(r"\bwho (made|created|built|developed|owns|runs)\b|\b(what|who)\b.*\b(actcheck|this (site|portal|app|website|tool)|it for|purpose|about)\b|"
                   r"\b(purpose|overview|introduc|explain actcheck|tell me about)", re.I)


def _key(q):
    return re.sub(r"[^a-z]", "", q.lower())


def search(question, k=2):
    exact = [g for g in GUIDE if _key(g[0]) == _key(question)]          # a quick button or the same question
    if exact:
        return exact
    if re.search(r"\bbilly\b|\bcan you\b|\bwho are you\b|\bwhat do you\b", question, re.I):
        return [g for g in GUIDE if g[0] == "What can BILLy do?"]
    if ABOUT.search(question) and not re.search(r"agent|cost|data|source|library|run log|daily|key|limit|bill type", question, re.I):
        return [g for g in GUIDE if g[0] == "What is ActCheck?"]
    from sklearn.feature_extraction.text import TfidfVectorizer
    docs = [(q + " ") * 2 + a for q, a in GUIDE]
    vec = TfidfVectorizer(analyzer=_tok, sublinear_tf=True)
    m = vec.fit_transform(docs + [question])
    sc = (m[:-1] @ m[-1].T).toarray().ravel()
    best = sorted(range(len(GUIDE)), key=lambda i: -sc[i])[:k]
    top = sc[best[0]] if best else 0
    return [GUIDE[i] for i in best if sc[i] > 0 and sc[i] >= 0.6 * top]


def suggestions():
    return ["What is ActCheck?", "What are the three agents?", "How do I send a report on a bill?", "How do I log in as a reviewer?",
            "How is the cost estimated?", "Where does the data come from?"]


def answer(history, question, live):
    if live:
        from agents import llm
        system = ("You are BILLy, the guide to the ActCheck portal. Answer briefly and plainly, only from the GUIDE below. If the answer is "
                  "not in the guide, say so and suggest opening a bill in the Review workspace. Never state a DBM position.\n\nGUIDE:\n"
                  + "\n".join(f"- {q} {a}" for q, a in GUIDE))
        msgs = [m for m in history if m["role"] in ("user", "assistant")][-8:] + [{"role": "user", "content": question}]
        text, _ = llm.chat("guide", system, msgs)
        return text
    hits = search(question)
    if not hits:
        return ("I'm not sure about that one. " + GUIDE[0][1].split(". ")[0] + ". Try asking what the three agents do, where the data "
                "comes from, how the cost is estimated, or what the Library and the Run log show.")
    return "\n\n".join(f"**{q}** {a}" for q, a in hits)
