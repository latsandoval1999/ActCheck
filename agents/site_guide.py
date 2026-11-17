"""What BILLy knows about ActCheck itself, for questions asked when no bill is open (Overview, How it Works and
the other pages). Search mode ranks these entries; AI mode answers from them only."""
import re

GUIDE = [
    ("What is ActCheck?", "ActCheck is an Agentic AI System for Philippine Legislative Review. It helps government analysts, first of "
     "all those who prepare the Department of Budget and Management's comments on bills, to trace a bill's history, see what changed "
     "from related measures, and assess its legal and budget implications, so they can give legislators timely, well-sourced comments. "
     "Three AI agents do the groundwork: TrAIce traces the bill, CompAIre spots the changes and AppraisAI weighs the impact. The "
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
    ("What are the three agents?", "TrAIce traces the bill: earlier versions, counterparts in the other chamber, refiled copies and the "
     "laws it touches. CompAIre spots the changes against the closest related measure and lists design options. AppraisAI weighs the "
     "impact: cost range, risks, overlaps, policy context and draft comments, then drafts the DBM memo and letter; a second AI reviewer "
     "(red-teamer) checks its draft."),
    ("What does TrAIce do?", "TrAIce (Evidence and Research) finds the bills whose wording is most similar, then labels each relationship "
     "(earlier version, counterpart, near-copy, competing, precedent) and the existing laws the bill amends or overlaps. Every link "
     "cites and quotes a section, and ActCheck checks each quote against the source."),
    ("What does CompAIre do?", "CompAIre (Diagnosis and Design) compares the bill with its closest related measure section by section: the "
     "problem it addresses, substantial differences (mandate, structure, salary grades, funding, duration) with their likely cost "
     "effect, and design options seen in related bills. ActCheck's own non-AI section matching is shown beside it."),
    ("What does AppraisAI do?", "AppraisAI (Appraisal and Governance) drafts the preliminary review: summary, history, differences, overlaps, "
     "fiscal implications, risks, policy context (LEDAC priority and the 2027 Budget Priorities Framework), a verification checklist "
     "and draft comments. After the analyst approves, it drafts the memorandum for the Secretary and the letter to Congress in DBM "
     "format. It never sets the DBM position."),
    ("How is the cost estimated?", "A fixed calculator, not the AI, estimates a first-year range two ways: staff costs from the 2026 salary "
     "schedule (NBC No. 601) plus benefits and running costs, and the running cost per authorized position of similar agencies in the "
     "FY 2026 budget (GAA and DBM Staffing Summary). COA audit reports are a cross-check. The agent may only quote these figures."),
    ("What is the daily check?", "Every day at 9:00 AM Manila time a scheduled job checks the data sources, looks for new House bills on the "
     "House documents server, reads them (including scanned pages), sorts them by type and lists them on the Bills page. It also "
     "catches up older House bills missing from the list. The Senate listing blocks GitHub's servers, so it is refreshed separately."),
    ("Where does the data come from?", "House bill PDFs from the House documents server; the Senate's public bill listing; Open Congress Data "
     "and the Philippine Legal Documents Library (BetterGov.PH); the FY 2026 GAA, DBM Staffing Summary and NBC No. 601; COA audit "
     "reports; the LEDAC Common Legislative Agenda; the DBM 2027 Budget Priorities Framework; and the PSA inflation report."),
    ("What is the Library?", "The Library has two parts. Review References lists the documents ActCheck relies on (budget, audit, policy, "
     "governance and legal references) with their date, purpose and a link. Full Text of Bills holds the bills, committee reports and "
     "laws ActCheck has read, divided into sections so every finding can point to an exact provision."),
    ("What is the Run log?", "The Run log has four parts: public reports sent from the Bills page (reviewers can open each one); the "
     "data sources with their role and when the daily check last checked them; the bills the agents have worked on, how far each "
     "has gone and when it was last run; and the Agentic AI Portfolio and Project Log of the major versions of ActCheck."),
    ("What are bill types?", "Each bill gets a scope (general or public, local application, or private or named grantee) and one of 18 "
     "content categories from rules on its title. 'Other or unclassified' holds titles no rule matches, such as bills on sports, "
     "culture, or science that use none of the key words; the analyst confirms the type during review."),
    ("What is the LEDAC flag?", "Bills related by title to the 44 Common Legislative Agenda measures identified by the LEDAC on 30 September "
     "2025 are flagged 'LEDAC priority' on the Bills page; the analyst confirms the match."),
    ("How do I review a bill?", "Click 'Reviewer Log In' at the top right (or Log In on any bill), open the Bills page, click Review on a bill, then work through "
     "the five steps in the Review workspace. Each step ends with a checklist that unlocks the next one."),
    ("How can the public share inputs on a bill?", "On the Bills page, click Report on any bill. The bill's number and title are filled in; "
     "choose the part of the review it concerns (TrAIce: legislative history; CompAIre: comparison and policy design; AppraisAI: cost, overlap or duplication, implementation or governance risk; or Others) and the topic, write a message "
     "and attach files if you like. Name, email and contact number are optional and seen only by reviewers. Reports are kept in a "
     "Google Sheet so they survive restarts, and reviewers see a clickable notice in the part of the Review workspace each report concerns."),
    ("Who decides the DBM position?", "Only the analyst. The agents prepare evidence and drafts; the analyst approves each step, sets the "
     "position and finalizes the memo and letter. The letter unlocks only after the position is set."),
    ("What are the safeguards?", "Every claim cites and quotes a source and the quote is checked; peso figures must come from the cost "
     "calculator or the bill; drafts may not contain positions, officials' names or signatures; a second AI reviewer checks the draft; "
     "checklists gate each step; reviewers can report problems; everything is logged. ActCheck follows the DICT-CSC Joint Memorandum "
     "Circular No. 003, s. 2026 on responsible AI in government."),
    ("What are the limits?", "It is a prototype: agents are tested on bills creating agencies; bill types come from title rules; the cost "
     "range is order-of-magnitude; House lists have gaps that the daily catch-up is filling; Senate updates need a manual refresh; "
     "reviews saved on the hosted site reset when it restarts."),
    ("Does it need an AI key?", "No. Without a key, each step shows ActCheck's own rule-based draft and BILLy searches the site. "
     "With an Anthropic key, reviewers can run the agents on the site; TrAIce outputs prepared by Claude can also be saved with ActCheck."),
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
