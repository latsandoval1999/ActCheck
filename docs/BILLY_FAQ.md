# BILLy FAQ

What BILLy knows about ActCheck. BILLy answers from these entries (data/reference/billy_faq.json) and the guide in agents/site_guide.py.

## About ActCheck

**Who is ActCheck for?** Mainly for government analysts who prepare comments on bills, especially those preparing the Department of Budget and Management's position papers. Civil society organizations and other members of the public can also browse every bill and send inputs with the Report button.

**Why was ActCheck made?** Preparing a DBM position paper on a bill takes up to 39 working days and 20 steps under the DBM Citizen's Charter (CY 2026). The evidence is scattered: two chamber websites, three Congresses, refiled and substitute versions, existing laws and budget data. ActCheck gathers that evidence and drafts the groundwork so analysts can spend their time on judgment.

**Is ActCheck an official government website?** No. It is a student prototype made for PP5538 (Lee Kuan Yew School of Public Policy, National University of Singapore). It is not operated by the House of Representatives, the Senate or the DBM, and nothing on it is an official DBM position.

**What does agentic AI mean here?** Each agent is given a role, tools and rules, and carries out several steps on its own: it gathers evidence, labels it, quotes the source, and checks its own output against rules before showing it. Unlike a chatbot, it works through a defined workflow with human approval gates between steps.

**What are the main parts of the portal?** Overview (summary, bills by type, and bills slated for review), Bills (every House and Senate bill of the 18th to 20th Congress, starting with the bills recommended for review), Review workspace (for reviewers: four review steps), How it Works (the process and the agents), Library (Review References and Full Text of Bills) and Run log (public reports, data sources, agent runs and the project log). BILLy is available on every page.

**What do the numbers on the Overview mean?** Bills listed is every House and Senate bill of the 18th to 20th Congress found in public sources. Bills in the 20th Congress counts the current Congress by chamber. New bills from the daily run shows what the latest daily check found. Bills slated for review counts the bills in the Review workspace.

**What does 'Trace the bill. Spot the changes. Weigh the impact.' mean?** These are the three agents' jobs: TrAIce traces the bill's history, CompAIre spots what changed against related bills, and ApprAIsal weighs the legal and budget impact.

**What happens when I first open ActCheck?** A welcome window from BILLy asks whether you are a Public Visitor (the public view, with reporting on bills) or an Analyst (the Review workspace). Your choice opens that view. You can switch later with the Reviewer Log In or Log Out button at the top right.

## Public users

**Can anyone use ActCheck?** Yes. Anyone can browse the Overview, Bills, How it Works, Library and Run log, open bill details and PDFs, ask BILLy, and send a report on a bill. Only reviewers use the Review workspace.

**How do I find a bill?** Open the Bills page. It starts with the bills ActCheck recommends for review, each with a one-sentence reason (stage, LEDAC or budget priority, whether it creates an agency, similar bills, public reports). Use any filter or the search box, or click Show all bills, to see every bill.

**How do I read a bill?** On the Bills page, click PDF in the View bill column to open the official document. Click the title for the bill's details. For bills whose text ActCheck has read, the Library's Full Text of Bills shows the text section by section.

**What information does each bill row show?** The bill number, the full title, the filing date and principal author (with Representative or Senator), the bill type, its status group and stage, a link to the PDF, and buttons to review (reviewers) or report (public).

**How do I send a report on a bill?** Click Report on the bill's row. The bill number and title are filled in. Choose the part of the review your report concerns (TrAIce: legislative history; CompAIre: comparison and policy design; ApprAIsal: cost, overlap or implementation risk; or Others) and the topic, write your message, and attach files if you like. Your name, email and contact number are optional.

**What happens to my report?** It is saved in ActCheck's Google Sheet and appears in the Run log's Public reports list. Reviewers see it as a notice in the step of the Review workspace it concerns, so it reaches them while they analyse the bill. Treat it as an input to the review, not a decision.

**Who sees my contact details?** Only logged-in reviewers. Contact details are optional, never published, and used only to follow up on your report, with your consent under the Data Privacy Act of 2012.

**What files can I attach to a report?** PDF, Word, Excel, CSV, text and image files (PNG or JPG), up to 10 MB each.

**Is there a limit to reports?** Up to five reports per visit, to prevent spam. You can come back later to send more.

**Can I see other people's reports?** The Run log lists which bills received reports and their topics. The content of each report is visible to reviewers only.

## Reviewers

**How do I log in as a reviewer?** Click Reviewer Log In at the top right, or Log In on any bill. For this course prototype there is no password. Click Log Out at the top right to return to the public view.

**How do I start a review?** Log in, open the Bills page and click Review on a bill (the page starts with the bills recommended for review). If ActCheck does not have the bill's text yet, it gets it from the official source. The bill then appears under 'Bills under review' with a status box: red for not yet started, yellow for ongoing, green when the memo and letter are drafted.

**What are the four steps in the Review workspace?** Step 1 TrAIce traces the bill (memo Parts I to III); Step 2 CompAIre spots the changes and recommends design options (Part IV); Step 3 ApprAIsal weighs the impact: budgetary requirements, possible duplication under RA No. 12231, the proposed recommendation and the DBM bureaus to consult (Parts V to VII); Step 4 Memo and letter, where the reviewer confirms the recommendation, edits and downloads the DBM-format memo and letter. Each step ends with a checklist that unlocks the next one.

**Why are some steps locked?** Each step ends with a reviewer checklist. The next step unlocks only when every item is ticked. This is the human approval gate: nothing moves forward until the reviewer has checked it.

**What is the reviewer checklist?** A short list at the end of each step. A red box with a white x means not yet done; a green box with a white check means done. Under the items are the points to check: for TrAIce, what is established, contested or cannot be established; for CompAIre, the theory of change and its self-critique; for ApprAIsal, the Red-teamer's findings. Each checklist has a Notes and attachments box. When every item is ticked, the next step unlocks and the finished step folds up; click Show to open it again.

**How do I run an agent?** You usually don't need to. Outputs prepared by TrAIce, CompAIre and ApprAIsal (Claude) are saved with ActCheck three times a day for the bills in the Review workspace and appear in each step automatically. Until then, each step shows ActCheck's draft. With an Anthropic key under Reviewer settings, the Run button runs an agent on the site.

**Can I edit what the agents produce?** Yes. Each agent's output has an 'Edit this text (if needed)' box, and in Step 4 the 'Edit memo' and 'Edit letter' buttons open the full drafts for editing before download. The reviewer's edits are what go into the documents.

**How do I download the memo and letter?** In Step 4, after the Step 3 checklist is complete: confirm the recommendation (Part VII), review the draft memo shown on screen, click 'Edit memo' if changes are needed, then use the Word download button. The letter opens after the recommendation is confirmed.

**Where do I see public reports on a bill?** In the Review workspace, a highlighted notice appears in the step a report concerns (TrAIce, CompAIre, ApprAIsal, or the whole bill). Click it to read the report, including any contact details and attachments. All reports are also listed in the Run log.

**How do I report a problem with an agent's output?** Use the Notes and attachments box at the end of the step's checklist to record a correction, and edit the agent's text with 'Edit this text (if needed)'. Public reports from the Bills page appear as notices in the step they concern.

**Can I review a bill that does not create an agency?** Yes. TrAIce and CompAIre work on any bill with full text. ApprAIsal's cost estimate is mainly designed for new agencies, so the workspace shows a note when a bill is outside the pilot scope, and the estimate is not shown for bills that create a program rather than an office.

**How does ActCheck choose the bills recommended for review?** It looks at pending 20th Congress bills with full text and adds points for: how soon the bill may move (final stage, floor, committee), a LEDAC priority or an FY 2027 budget priority, creating a national agency or appropriating funds, several bills with the same title, and public reports. Bills with the same title are listed once. It is a starting point; the reviewer decides what to review.

**What do the colours beside a bill under review mean?** Red: not yet started. Yellow: ongoing (some checklist items ticked or text edited). Green: the memo and the letter are drafted, after the recommendation is confirmed.

**Is my review progress saved if the site restarts?** Yes. Ticks, notes, edits, bureau comments and the memo and letter are copied to the project's Google Sheet a few seconds after each change and come back when the site restarts. Files attached to checklists are not copied.

## The agents

**What are TrAIce's outputs?** A policy context (what the bill proposes, its alignment with the FY 2027 Budget Priorities Framework and the LEDAC agenda, and what the review should examine), the bill's legislative history, its Related Bills grouped by relationship (filed in a past Congress; same bill, filed again this Congress; merged into this bill; Senate or House version; alternative proposal; template it follows; not related), its Related Laws (amends or repeals, overlapping functions, referenced in the bill, template it follows), its fiscal requirements, and memo-ready Parts II (Salient Features) and III (Related Measures and Policy Considerations) that the reviewer can edit.

**How does TrAIce find related bills?** ActCheck first ranks bills by how similar their titles and text are across the 18th to 20th Congress and drafts each relationship. TrAIce (Claude) then reads the closest bills and laws, corrects the labels, and backs each link with a passage from the cited section; ActCheck checks every passage word for word.

**What is the red-teamer?** A permanent helper in ApprAIsal's team that attacks every ApprAIsal draft before the reviewer sees it. It looks for statements outside ApprAIsal's role (a DBM position, officials' names, political advice, personal details), figures not from the calculator, conflicts between Parts IV to VII (for example 'no objection as filed' while Part IV asks for amendments) and missing bureau referrals. Its verdict and findings appear in the Step 3 checklist; the reviewer decides what to change.

**Does ApprAIsal decide whether DBM supports a bill?** No. ApprAIsal proposes one of three recommendations: no objection; no objection, subject to amendments; or deferment until the issues are addressed. Only the analyst confirms it in Step 4, and the Secretary approves the position paper.

**Which AI model do the agents use?** Claude, by Anthropic. Outputs marked 'Prepared by TrAIce/CompAIre/ApprAIsal (Claude)' were prepared in scheduled Claude sessions under the project owner's subscription and saved after ActCheck's checks. The cost calculator and the similarity ranking are fixed calculations.

**Why does TrAIce mention the Government Optimization Act?** For bills that create or reorganize government bodies, TrAIce asks the reviewer to examine how the proposed functions fit with existing agencies and the government's intent to streamline agencies and reduce overlapping mandates under the Government Optimization Act (RA No. 12231). The law is listed under Review References in the Library.

**Can I edit TrAIce's output?** Yes. Under 'TrAIce Output and Reviewer Checklist', click 'Edit this text' to revise Parts II and III. Your edited text is used in the memorandum in Step 4; 'Reset to the TrAIce draft' brings back the agent's version.

**Does TrAIce show the quotes it used?** No. The passages are checked in the background. The page shows the section references, written as 'Section N (Section Title)', how many were verified, and a tag on each related bill: full text, scanned text or title only.

**What is TrAIce's evidence grade?** Each TrAIce output gets one grade, from A (strong) to D (weak), set by ActCheck, not by the agent. It adds up to 8 points: how the bill's text was read (official PDF or scanned copy), whether every cited passage was verified, how much of the mapping rests on full texts rather than titles, and how many points remain to confirm.

**Who prepares the TrAIce outputs marked 'Prepared by TrAIce (Claude)'?** A scheduled Claude session, run three times a day under the project owner's Claude subscription, prepares TrAIce, CompAIre and ApprAIsal outputs for the bills in the Review workspace, and TrAIce outputs for the pilot bills. A separate session runs the Red-teamer. ActCheck saves an output only when every cited passage and figure passes its checks.

**What does CompAIre produce?** Building on TrAIce's salient features, CompAIre states what the bill aims to address and compares each major provision with the related measure that offers a real alternative. Its table, Substantial Differences and Design Options, shows for each provision the related measure, the major differences, the recommended option (Retain provision, Adapt alternative, Adapt alternative with revisions, or Remove provision) and why, the trade-offs and the gaps to check. Its main output is memo Part IV (Comments and Recommendations), covering only the provisions that need a decision. Possible duplication of functions and cost effects go to ApprAIsal and are reviewed there.

**Is the evidence grade used for every agent?** Yes. TrAIce, CompAIre and ApprAIsal each show one grade (A Strong to D Weak) in their checklist, with the points and what kept the output from more points. ActCheck sets the grade, not the agent. The method is under Safeguards and Limits on the How it Works page.

**What does ApprAIsal produce?** ApprAIsal prepares memo Parts V to VII. Part V, Fiscal and Budgetary Requirements: an estimate of Personnel Services, MOOE and Capital Outlay for a new entity or positions, and a table of each fiscal item with the provision, what the bill provides, the recommended budgetary consideration, the recommendation on the budget and the GAA, and the risks. Part VI, Possible Duplication with Existing Agencies (when found): whether the bill changes or abolishes the existing body and, if not, an assessment under the Government Optimization Act (RA No. 12231). Part VII, Recommendation: one of three options (interpose no objection; no objection, subject to amendments; or deferment until the issues are addressed), which the reviewer confirms. It also lists the DBM bureaus to consult and compiles the memo without repeating statements.

**How are the bureaus' comments included without another log-in?** ApprAIsal lists the DBM bureaus and offices to consult, with the items for each. Under 'Bureau comments (if needed)' in Step 3, each bureau has a ready request to copy into the usual referral memo or e-mail, and a box to paste the reply when it arrives. The replies go into Part IV of the memo under 'Comments of the concerned bureaus'. Bureaus do not need an account.

**How does ApprAIsal choose the Budget and Management Bureau?** It reads the agencies named in the bill and matches them with the coverage lists in the DBM Central Office Directory (BMB-A to BMB-F and the Local Government and Regional Coordination Bureau). The bureau covering the agency whose budget the bill charges comes first (for example, BMB-C for a commission funded from the budgets of the Senate and the House of Representatives), then the bureau of the agency the new office is attached to, then bureaus of agencies the bill gives a role. The bureau's office e-mail address is shown with each request. When the bill names no covered agency, it asks the reviewer to confirm the bureau.

**How is the cost of a new agency estimated?** In the background, ActCheck sets a staffing structure for the headcount range (offices, officials, division chiefs and staff), computes Personnel Services from the 2026 salary schedule with mandatory benefits, and MOOE and Capital Outlay from DBM costing parameters (travel under EO No. 77, s. 2019; training under NBC No. 563; rent under the DBM-DPWH Joint Circular; vehicles under DBM Budget Circular Nos. 2022-1 and 2022-1A). It shows the PS, MOOE and CO summary; the assumptions and similar agencies are in a reference dropdown.

**What are 'established', 'contested' and 'cannot establish' in TrAIce's checklist?** Established: links whose cited passage was verified in a bill's full text. Contested: links that rest on a scanned or title-only source, a passage that was not verified, or a label that differs from ActCheck's draft; confirm these before relying on them. Cannot establish: what the data does not show, such as the bill's status after filing.

**What are the theory of change and the self-critique in CompAIre's checklist?** The theory of change states, in one line, how the bill is meant to work and the assumption most likely to fail. In the self-critique, CompAIre argues against each of its own recommendations and judges whether it still holds, holds only with a condition, or is reversed. ActCheck flags the critique if it looks too easy on itself, for example when nothing is ever weakened.

**Is ApprAIsal one agent or a team?** A team. ApprAIsal leads four helpers: Costing (the cost calculator), Duplication (overlap with existing agencies under RA No. 12231), Referral (the DBM bureaus to consult, by their coverage) and Recommendation (the Part VII option). A Red-teamer checks every draft. They work in the background; their results appear in Step 3.

## Cost estimate

**How reliable is the cost estimate?** It is a first-year range for a new office, not a budget proposal. A fixed calculator computes it from the 2026 salary schedule and DBM costing parameters, with similar agencies in the FY 2026 budget as a cross-check. Reviewers should check the staffing assumptions against the agency's own plan.

**What is Method A and Method B?** Method A builds the cost from staff: positions and salary grades, the 2026 salary schedule (NBC No. 601), mandatory benefits, operating costs and equipment. Method B compares what similar agencies spend per authorized position in the FY 2026 budget (GAA and DBM Staffing Summary); it is shown as a cross-check.

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

**What does the Run log show?** Public reports received (reviewers can open them), whether the Google Sheet that keeps reports and review progress is connected, the data sources and when they were last checked, the outputs prepared by each agent (Claude) with their grades and the Red-teamer's verdict, and the project log.

**What is the Agentic AI Portfolio and Project Log?** A dated summary of the major versions of ActCheck (8 and 16 November 2026), listing what was added, revised or removed for each agent and the portal, and the measured effect on the test bills.

**What is How it Works?** A page showing where ActCheck fits in the DBM Citizen's Charter process (39 working days, about 25 with ActCheck as an illustrative target), what each agent does and its safeguards, and the Responsible AI measures.

## Safeguards and privacy

**How does ActCheck prevent made-up citations?** Every link to a bill or law must be backed by a short passage from the cited section, and ActCheck checks each passage word for word against the stored text; figures must match exactly. An output with a passage that is not found is not saved, and anything unverified shows as 'contested' in the TrAIce checklist.

**Does ActCheck store personal data?** Only optional contact details in public reports, kept in a private Google Sheet and visible to reviewers only. Officials' names are not used in drafts, and bill texts are public documents.

**Which guidelines does ActCheck follow?** The DICT-CSC Joint Memorandum Circular No. 003, s. 2026 on ethical and responsible AI in government, NPC Advisory No. 2024-04 on AI and the Data Privacy Act, and the Data Privacy Act of 2012.

**Is every output labelled as AI-assisted?** Yes. Every draft is marked as an AI-assisted preliminary draft for DBM reviewer validation, not an official position.

**What can't ActCheck be trusted to do?** It cannot guarantee it found every related bill, judge the political merits of a bill, replace the bureaus' expertise, or decide the DBM position. Scanned PDFs may contain reading errors, so passages from them are marked contested and should be checked against the original.

## Using BILLy

**How do I ask BILLy about a specific bill?** Log in as a reviewer and open the bill in the Review workspace. BILLy then answers from that bill's sections and the agents' findings, and points to the section it used.

**Why does BILLy say it is not sure?** BILLy answers only from ActCheck's guide or the open bill, so it does not guess. Try rephrasing, or ask about the agents, the data sources, the cost estimate, the Library or the Run log.
