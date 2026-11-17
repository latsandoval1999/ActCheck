# BILLy FAQ

Everything BILLy can answer about ActCheck when no bill is open. Core guide entries are in `agents/site_guide.py`; the longer FAQ is in `data/reference/billy_faq.json` (edit that file to add questions).

## Core guide

**What is ActCheck?** ActCheck is an Agentic AI System for Philippine Legislative Review. It helps government analysts, first of all those who prepare the Department of Budget and Management's comments on bills, to trace a bill's history, see what changed from related measures, and assess its legal and budget implications, so they can give legislators timely, well-sourced comments. Three AI agents do the groundwork: TrAIce traces the bill, CompAIre spots the changes and AppraisAI weighs the impact. The analyst checks and approves every step and alone decides the DBM position. Every finding cites the bill or law it comes from, and every output is an AI-assisted preliminary draft for reviewer validation. ActCheck is a student prototype for PP5538 (Lee Kuan Yew School of Public Policy), not an official government website.

**What can BILLy do?** BILLy is ActCheck's guide. On any page it answers questions about the portal: the agents, the data sources, the cost estimate, the Library and the Run log. When a bill is open in the Review workspace, BILLy answers questions about that bill from its own sections and the agents' findings, and points to the section it used.

**What problem does it address?** DBM must comment on a large volume of bills. The DBM Citizen's Charter (CY 2026) gives 39 working days and 20 steps for a position paper. The evidence for each review is scattered across two chamber websites, three Congresses, refiled and substitute versions, existing laws and budget data, and bills that create agencies often state no cost.

**Which bills are covered?** The Bills page lists every House and Senate bill of the 18th to 20th Congress from public sources. The agents are tested first on bills that create a national government agency, in any sector; other bills with full text can be reviewed, but the cost estimate applies only to new agencies.

**What are the three agents?** TrAIce traces the bill: earlier versions, counterparts in the other chamber, refiled copies and the laws it touches. CompAIre spots the changes against the closest related measure and lists design options. AppraisAI weighs the impact: cost range, risks, overlaps, policy context and draft comments, then drafts the DBM memo and letter; a second AI reviewer (red-teamer) checks its draft.

**What does TrAIce do?** TrAIce (Evidence and Research) finds the bills whose wording is most similar, then labels each relationship (earlier version, counterpart, near-copy, competing, precedent) and the existing laws the bill amends or overlaps. Every link cites and quotes a section, and ActCheck checks each quote against the source.

**What does CompAIre do?** CompAIre (Diagnosis and Design) compares the bill with its closest related measure section by section: the problem it addresses, substantial differences (mandate, structure, salary grades, funding, duration) with their likely cost effect, and design options seen in related bills. ActCheck's own non-AI section matching is shown beside it.

**What does AppraisAI do?** AppraisAI (Appraisal and Governance) drafts the preliminary review: summary, history, differences, overlaps, fiscal implications, risks, policy context (LEDAC priority and the 2027 Budget Priorities Framework), a verification checklist and draft comments. After the analyst approves, it drafts the memorandum for the Secretary and the letter to Congress in DBM format. It never sets the DBM position.

**How is the cost estimated?** A fixed calculator, not the AI, estimates a first-year range two ways: staff costs from the 2026 salary schedule (NBC No. 601) plus benefits and running costs, and the running cost per authorized position of similar agencies in the FY 2026 budget (GAA and DBM Staffing Summary). COA audit reports are a cross-check. The agent may only quote these figures.

**What is the daily check?** Every day at 9:00 AM Manila time a scheduled job checks the data sources, looks for new House bills on the House documents server, reads them (including scanned pages), sorts them by type and lists them on the Bills page. It also catches up older House bills missing from the list. The Senate listing blocks GitHub's servers, so it is refreshed separately.

**Where does the data come from?** House bill PDFs from the House documents server; the Senate's public bill listing; Open Congress Data and the Philippine Legal Documents Library (BetterGov.PH); the FY 2026 GAA, DBM Staffing Summary and NBC No. 601; COA audit reports; the LEDAC Common Legislative Agenda; the DBM 2027 Budget Priorities Framework; and the PSA inflation report.

**What is the Library?** The Library has two parts. Review References lists the documents ActCheck relies on (budget, audit, policy, governance and legal references) with their date, purpose and a link. Full Text of Bills holds the bills, committee reports and laws ActCheck has read, divided into sections so every finding can point to an exact provision.

**What is the Run log?** The Run log has four parts: public reports sent from the Bills page (reviewers can open each one); the data sources with their role and when the daily check last checked them; the bills the agents have worked on, how far each has gone and when it was last run; and the Agentic AI Portfolio and Project Log of the major versions of ActCheck.

**What are bill types?** Each bill gets a scope (general or public, local application, or private or named grantee) and one of 18 content categories from rules on its title. 'Other or unclassified' holds titles no rule matches, such as bills on sports, culture, or science that use none of the key words; the analyst confirms the type during review.

**What is the LEDAC flag?** Bills related by title to the 44 Common Legislative Agenda measures identified by the LEDAC on 30 September 2025 are flagged 'LEDAC priority' on the Bills page; the analyst confirms the match.

**How do I review a bill?** Click 'Reviewer Log In' at the top right (or Log In on any bill), open the Bills page, click Review on a bill, then work through the five steps in the Review workspace. Each step ends with a checklist that unlocks the next one.

**How can the public share inputs on a bill?** On the Bills page, click Report on any bill. The bill's number and title are filled in; choose the part of the review it concerns (TrAIce: legislative history; CompAIre: comparison and policy design; AppraisAI: cost, overlap or duplication, implementation or governance risk; or Others) and the topic, write a message and attach files if you like. Name, email and contact number are optional and seen only by reviewers. Reports are kept in a Google Sheet so they survive restarts, and reviewers see a clickable notice in the part of the Review workspace each report concerns.

**Who decides the DBM position?** Only the analyst. The agents prepare evidence and drafts; the analyst approves each step, sets the position and finalizes the memo and letter. The letter unlocks only after the position is set.

**What are the safeguards?** Every claim cites and quotes a source and the quote is checked; peso figures must come from the cost calculator or the bill; drafts may not contain positions, officials' names or signatures; a second AI reviewer checks the draft; checklists gate each step; reviewers can report problems; everything is logged. ActCheck follows the DICT-CSC Joint Memorandum Circular No. 003, s. 2026 on responsible AI in government.

**What are the limits?** It is a prototype: agents are tested on bills creating agencies; bill types come from title rules; the cost range is order-of-magnitude; House lists have gaps that the daily catch-up is filling; Senate updates need a manual refresh; reviews saved on the hosted site reset when it restarts.

**Does it need an AI key?** No. Without a key, ActCheck shows its own rule-based analysis, BILLy searches, and each agent step can be run in a Claude chat through the free route. With an Anthropic key, reviewers can run the agents on the site.

## About ActCheck

**Who is ActCheck for?** Mainly for government analysts who prepare comments on bills, especially those preparing the Department of Budget and Management's position papers. Civil society organizations and other members of the public can also browse every bill and send inputs with the Report button.

**Why was ActCheck made?** Preparing a DBM position paper on a bill takes up to 39 working days and 20 steps under the DBM Citizen's Charter (CY 2026). The evidence is scattered: two chamber websites, three Congresses, refiled and substitute versions, existing laws and budget data. ActCheck gathers that evidence and drafts the groundwork so analysts can spend their time on judgment.

**Is ActCheck an official government website?** No. It is a student prototype made for PP5538 (Lee Kuan Yew School of Public Policy, National University of Singapore). It is not operated by the House of Representatives, the Senate or the DBM, and nothing on it is an official DBM position.

**What does agentic AI mean here?** Each agent is given a role, tools and rules, and carries out several steps on its own: it gathers evidence, labels it, quotes the source, and checks its own output against rules before showing it. Unlike a chatbot, it works through a defined workflow with human approval gates between steps.

**What are the main parts of the portal?** Overview (summary and bills by type), Bills (every House and Senate bill of the 18th to 20th Congress), Review workspace (for reviewers: the five review steps), How it Works (the process and the agents), Library (Review References and Full Text of Bills) and Run log (public reports, data sources, agent runs and the project log). BILLy, the guide, is available on every page.

**What do the numbers on the Overview mean?** Bills listed is every House and Senate bill of the 18th to 20th Congress found in the public sources. Bills in the 20th Congress counts the current Congress by chamber. New bills from the daily run shows bills found by the latest daily check, and how many older House bills the catch-up has added.

**What does 'Trace the bill. Spot the changes. Weigh the impact.' mean?** These are the three agents' jobs: TrAIce traces the bill's history, CompAIre spots what changed against related bills, and AppraisAI weighs the legal and budget impact.

## Public users

**Can anyone use ActCheck?** Yes. Anyone can browse the Overview, Bills, How it Works, Library and Run log, open bill details and PDFs, ask BILLy, and send a report on a bill. Only reviewers use the Review workspace.

**How do I find a bill?** Open the Bills page. Type a bill number (e.g. HB 2322), words from the title, a subject or an author's name in the search box, or narrow the list with the Congress, Bill type, Category, Status and Applies to filters. Turn on 'Full text only' to see only bills whose text ActCheck has read.

**How do I read a bill?** On the Bills page, click PDF in the View bill column to open the official document. Click the title for the bill's details. For bills whose text ActCheck has read, the Library's Full Text of Bills shows the text section by section.

**What information does each bill row show?** The bill number, the full title, the filing date and principal author (with Representative or Senator), the bill type, its status group and stage, a link to the PDF, and buttons to review (reviewers) or report (public).

**How do I send a report on a bill?** Click Report on the bill's row. The bill number and title are filled in. Choose the part of the review your report concerns (TrAIce: legislative history; CompAIre: comparison and policy design; AppraisAI: cost, overlap or implementation risk; or Others) and the topic, write your message, and attach files if you like. Your name, email and contact number are optional.

**What happens to my report?** It is saved in ActCheck's Google Sheet and appears in the Run log's Public reports list. Reviewers see it as a notice in the step of the Review workspace it concerns, so it reaches them while they analyse the bill. Treat it as an input to the review, not a decision.

**Who sees my contact details?** Only logged-in reviewers. Contact details are optional, never published, and used only to follow up on your report, with your consent under the Data Privacy Act of 2012.

**What files can I attach to a report?** PDF, Word, Excel, CSV, text and image files (PNG or JPG), up to 10 MB each.

**Is there a limit to reports?** Up to five reports per visit, to prevent spam. You can come back later to send more.

**Can I see other people's reports?** The Run log lists which bills received reports and their topics. The content of each report is visible to reviewers only.

## Reviewers

**How do I log in as a reviewer?** Click Reviewer Log In at the top right, or Log In on any bill. For this course prototype there is no password. Click Log Out at the top right to return to the public view.

**How do I start a review?** Log in, open the Bills page and click Review on a bill. If ActCheck does not have its text yet, it fetches it from the official source. The bill then appears in the Review workspace under 'Bills under review'.

**What are the five steps in the Review workspace?** Step 1 TrAIce traces the bill; Step 2 CompAIre spots the changes; Step 3 AppraisAI weighs the impact, with a second AI reviewer; Step 4 Comments and report, which the reviewer edits and exports; Step 5 the memorandum and letter in DBM format.

**Why are some steps locked?** Each step ends with a reviewer checklist. The next step unlocks only when every item is ticked. This is the human approval gate: nothing moves forward until the reviewer has checked it.

**What is the reviewer checklist?** A list of checks at the end of each step, such as 'the quotes match the bill' or 'the cost assumptions marked to verify have been checked'. Each item can carry a note and an uploaded file as evidence of the check.

**How do I run an agent?** Click the Run button in the step. This needs an AI key under Reviewer settings (the arrow at the top left). Without a key, use the free route: copy the prepared prompt into your Claude chat and paste the answer back; ActCheck checks it the same way.

**What is the free route?** A way to use the agents without an API key. ActCheck prepares the agent's full instructions and evidence; you run them in a Claude chat and paste the reply back. The same citation and rule checks are applied to the pasted answer.

**Can I edit what the agents produce?** Yes. Comments in Step 4 are editable in a table, and the memo and letter fields in Step 5 are filled in for you to change before download. The reviewer's edits are what go into the documents.

**How do I download the memo and letter?** In Step 5, after Step 3 is approved, fill in or edit the fields and click the Word download buttons. The memo follows the DBM position-paper format; the letter opens only after you set the DBM position.

**Where do I see public reports on a bill?** In the Review workspace, a highlighted notice appears in the step a report concerns (TrAIce, CompAIre, AppraisAI, or the whole bill). Click it to read the report, including any contact details and attachments. All reports are also listed in the Run log.

**How do I report a problem with an agent's output?** Use 'Report a problem with this output' in the step. The note is logged with the bill so the problem can be fixed and documented.

**Can I review a bill that does not create an agency?** Yes. TrAIce and CompAIre work on any bill with full text. AppraisAI's cost estimate is designed for bills that create a government agency, so the workspace warns you when a bill is outside that pilot scope.

## The agents

**What are TrAIce's outputs?** A list of related measures with their relationship (earlier version, counterpart in the other chamber, refiled near-copy, competing design, precedent or model, unrelated), the existing laws the bill amends or overlaps with, a quoted section for each finding, and the gaps it could not establish.

**How does TrAIce find related bills?** ActCheck first ranks bills by similarity of title and text across the 18th to 20th Congress, without AI. TrAIce then reads the closest ones and labels each relationship, quoting a section as evidence.

**What are CompAIre's outputs?** The problem the bill addresses, the substantial differences from the closest related measure with their likely effect on cost, design options found in related bills, and corrections to ActCheck's own non-AI section matching.

**What are AppraisAI's outputs?** A preliminary review: summary, legislative history, differences, overlaps, fiscal implications with a cost range, risks, policy context, draft comments and a verification checklist. After approval it drafts the memorandum and the letter in DBM format.

**What is the red-teamer?** A second AI reviewer that checks AppraisAI's draft for unsupported figures, unchecked quotes, overstated claims and anything that reads like an official DBM position. It recommends whether the draft is ready or needs revision; the human reviewer decides.

**Does AppraisAI decide whether DBM supports a bill?** No. It lays out observations and options ('DBM may consider...'). Only the analyst sets the DBM position, and the Secretary approves the position paper.

**Which AI model do the agents use?** Claude, by Anthropic, either through an API key added under Reviewer settings or through the free route in a Claude chat. The cost calculator and the similarity ranking do not use AI.

## Cost estimate

**How reliable is the cost estimate?** It is a first-year range, not a forecast. It is computed by a fixed calculator from public budget data and comparator agencies, and every judgement assumption is marked 'to verify'. Reviewers should check the assumptions against the agency's actual staffing plan.

**What is Method A and Method B?** Method A builds the cost from staff: positions and salary grades from the bill, the 2026 salary schedule (NBC No. 601), mandatory benefits and running costs. Method B uses what similar agencies spend per authorized position in the FY 2026 budget (GAA and DBM Staffing Summary).

**Why does the cost appear as a range?** Bills that create agencies rarely state staffing or cost. The range reflects different comparator agencies and assumptions; the low and high ends show how much the answer depends on them.

**Can the AI change the cost figures?** No. The AI may only quote figures from the calculator or the bill. The checker flags any peso amount that does not come from those sources.

## Bills and status

**What do the status groups mean?** Pending: filed and still moving (filed, in committee, on reading, in the other chamber, in bicameral conference or sent to the President). Enacted: approved by the President, enrolled, approved with vetoes or lapsed into law. Consolidated or substituted: absorbed into a committee report or another bill. Not enacted: vetoed, withdrawn, or the Congress ended without action.

**Where does a bill's status come from?** From the bill list in the public sources. Where it is missing, ActCheck fills it from Republic Act records (which bills an Act came from) or marks 20th Congress bills with no later stage as Pending, Filed. The bill's details show which source was used.

**Why do older bills show 'Congressional session ended'?** Bills of the 18th and 19th Congress that did not become law or were not absorbed into another measure lapsed when that Congress ended.

**Where does the filing date come from?** From the bill list, or from the House receiving stamp on page 1 ('RECEIVED, DATE 09 NOV 2026'), read from the PDF and checked against the dates of the bills numbered just before and after. If the stamp cannot be read, the row says 'date not clearly visible; verify in file'.

**What is the Category filter?** It groups bills by what they propose, such as government organization and mandates, taxation, public programs and benefits, or commemorations. Categories are assigned from the title by rules and should be confirmed in review.

**What does 'Applies to' mean?** Whether the bill is general or public in application, or local or private, such as a franchise or a measure for one locality.

**What does 'Listing only' mean?** ActCheck knows the bill from the official list but has not read its text yet. Reviewers can click Review to fetch it.

## Data and updates

**How often is ActCheck updated?** The daily check runs every day at 9:00 AM Manila time. The Senate list is refreshed every Monday, and the Republic Acts library weekly.

**Why are there no new bills some days?** The House uploads bill PDFs a few days after filing, and Congress may be in recess. The daily check reports the highest bill number published; a blocked source is reported as unavailable, never as 'no new bills'.

**What is the catch-up?** Each daily run also fetches older House bills missing from the list, a few hundred at a time, until the 20th Congress is complete.

**Does ActCheck get around website blocks?** No. When a site refuses automated visitors, ActCheck reports it and uses another public source; it never bypasses a bot check. It also respects robots.txt and each site's terms.

**Are very long bills included?** Yes, but very long documents, such as the General Appropriations Bill, are shortened in ActCheck's text so the portal stays within its hosting limits. The PDF link always opens the full official text.

## Library and Run log

**What are Review References?** The public documents ActCheck relies on, grouped by purpose (process, costing, fiscal and policy context, governance, evaluation, legislative data), each with its issuer, date, purpose and a link. Documents whose text ActCheck reads have a Read button.

**What is in Full Text of Bills?** The bills, substitute bills, committee reports and laws ActCheck has read, split into sections so findings can cite the exact provision. Search by number or title, filter by type and group, and click a title to read it.

**What does the Run log show?** Public reports received, the data sources with their role and when they were last checked, the bills the agents have worked on and how far each has gone, and the Agentic AI Portfolio and Project Log of the major versions of ActCheck.

**What is the Agentic AI Portfolio and Project Log?** A dated summary of the major versions of ActCheck (8 and 16 November 2026), listing what was added, revised or removed for each agent and the portal, and the measured effect on the test bills.

**What is How it Works?** A page showing where ActCheck fits in the DBM Citizen's Charter process (39 working days, about 25 with ActCheck as an illustrative target), what each agent does and its safeguards, and the Responsible AI measures.

## Safeguards and privacy

**How does ActCheck prevent made-up citations?** Every finding must quote a section, and ActCheck checks each quote word for word against the stored text. Quotes that do not match are flagged before the reviewer sees the output as verified.

**Does ActCheck store personal data?** Only optional contact details in public reports, kept in a private Google Sheet and visible to reviewers only. Officials' names are not used in drafts, and bill texts are public documents.

**Which guidelines does ActCheck follow?** The DICT-CSC Joint Memorandum Circular No. 003, s. 2026 on ethical and responsible AI in government, NPC Advisory No. 2024-04 on AI and the Data Privacy Act, and the Data Privacy Act of 2012.

**Is every output labelled as AI-assisted?** Yes. Every draft is marked as an AI-assisted preliminary draft for DBM reviewer validation, not an official position.

**What can't ActCheck be trusted to do?** It cannot guarantee it found every related bill, judge the political merits of a bill, replace the bureaus' expertise, or decide the DBM position. Scanned PDFs may contain reading errors, so quotes from them should be checked against the original.

## Using BILLy

**How do I ask BILLy about a specific bill?** Log in as a reviewer and open the bill in the Review workspace. BILLy then answers from that bill's sections and the agents' findings, and points to the section it used.

**Why does BILLy say it is not sure?** BILLy answers only from ActCheck's guide or the open bill, so it does not guess. Try rephrasing, or ask about the agents, the data sources, the cost estimate, the Library or the Run log.
