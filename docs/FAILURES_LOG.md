# Real failures found and fixed, by agent

For the portfolio templates (Section 6 Testing results and Section 7 Failures found and corrections made).
Every entry is a failure that actually happened in ActCheck, how it was caught, and the rule or fix that now
prevents it. "Held" means a safeguard stopped the failure before it reached the reviewer; "Failed" means it
got through and was fixed afterwards. New failures are added here as they are found (most recent last in each table).

Sources: `docs/VERSION_LOG.md`, `docs/PROJECT_LOG.md`, `runs_archive/`, `logs/*.jsonl`, the test suite (`tests/`).

## TrAIce (Agent 1): Evidence and Research

Failure the course asks this agent to catch: a fabricated citation.

| Date | Test or how found | What happened | Result | Rule or fix |
|---|---|---|---|---|
| 8 Nov 2026 | Live run v1 on HB 2322 (separate Claude instance, prompt only) | The agent itself reported three gaps: the Senate committee report's chamber unknown; RA 11899 (EDCOM 2) forced into "unrelated"; HB 11060 listed by the baseline but its text missing | Failed (reported by the agent, not hidden) | v2: new label for a model law; committee-report front matter made citable; up to 8 related bills sent with key sections. v2 run: 12/12 citations verified, committee report read correctly |
| 8 Nov 2026 | Same run | The rule baseline used a label ("same subject, competing or related design") that is not one of the agent's labels; the agent flagged it | Held (agent flagged) | Labels mapped to the agent's set (v3: `OLD` map in `agents/traice.py`) |
| 17 Nov 2026 | Comparing the rule draft (no AI) with Claude's output on HB 2322 | The rule draft missed HB 5106 (an alternative proposal, 19% wording in common) and RA No. 12022's oversight committee (overlapping functions); Claude found both | Failed (rules) / Held (Claude) | Kept as the main evidence that the AI step adds value; rule draft labelled "Draft prepared by ActCheck's rules (no AI)" and capped at grade B |
| 17 Nov 2026 | Reviewer reading the rule draft | Mislabels by the rules: HB 5129 (82% identical, same chamber and Congress) labelled "Alternative proposal"; HB 6789's identically titled House bills labelled "Not related"; RA 11899 labelled "Overlapping functions" instead of "Template it follows" | Failed | Rules: same chamber + same Congress + ≥70% wording → "Same bill, filed again" (or "Merged into this bill" for a substitute); identical title → by chamber and Congress; same type of body on a different subject → "Template it follows" |
| 17 Nov 2026 | Live site check after the v3 release | Honesty failure: bills with an old v2 run showed the badge "Prepared by TrAIce (Claude)" although most of the page was drafted by rules | Failed | Badge now says which parts Claude prepared; a saved v3 output takes precedence over an older v2 run |
| 17 Nov 2026 | **Red-team: altered figure in a quote** (fabricated-citation test) | A quote from RA No. 8435, Section 116 with the amount changed from P20 million to P50 million passed the fuzzy quote check as "verified" | **Failed** | Figures and number words in a quote must now match the cited section exactly (`agents/verify.py`, `figures()`); regression test `test_altered_figure_in_quote_is_caught`. Same test now: "quote not found in section" |
| 17 Nov 2026 | Red-team: citation to a bill that does not exist (HB-19-4321:s4) and to a section beyond the law's end (RA-8435:s250) | Both flagged "section does not exist" | Held | — |
| 17 Nov 2026 | Reviewer reading drafted text | Rule-drafted sentences were garbled: "seeks to promot", "a AGRICOM", truncated purposes, OCR noise in quotes | Failed | Verb and article fixes, OCR clean-up, and the proposal drawn from the bill's own purpose clause |
| 17 Nov 2026 | Proofreading check, first run | 5,202 findings, most of them false (OCR letters, place names such as "Bolo Bolo", "one hundred twenty (120)" read as "twenty (120)") | Failed (too noisy) | Full number phrases parsed; text-layer and OCR confusions skipped; only insert/delete/swap edits in full texts; 859 findings, with a Likely/Possible confidence |
| 17 Nov 2026 | Claude run on HB 9897 (100 sections) | The prompt dropped the bill's appropriations, transfer and oversight sections (Sections 70, 81, 93): the section cap counted all sections before choosing the key ones, so sections after the 60th never reached the agent | Failed (caught while preparing the run) | The cap now counts only the sections kept (`agents/pipeline_agents.py`); bills of up to 25 sections are sent whole |
| 17 Nov 2026 | Rule draft for HB 9897 | The rule draft called the Department "a 6-member Department", taking the count from the oversight committee | Failed (rules) | Member counts used only for commissions, councils, boards and committees |


## CompAIre (Agent 2): Diagnosis and Design

Failures the course asks this agent to catch: fake-distinct options; a flattering self-critique.

| Date | Test or how found | What happened | Result | Rule or fix |
|---|---|---|---|---|
| 8 Nov 2026 | Live run v1, HB 2322 vs SB 1624 | The rule baseline marked Duration, Advisory Council and Technical Secretariat clauses "changed" although equal in substance, and paired Effectivity with the Repealing clause because of OCR | Held (the agent corrected 10 baseline pairings) | Agent's baseline corrections kept; checker flags differences claimed in near-identical sections |
| 8 Nov 2026 | Reviewer reading the v1 output | Wrong fiscal direction: SB 1624's added operational tasks (farmer training, identifying markets) labelled "likely lowers cost"; added tasks normally raise cost | Failed (fixed in v3) | v3: every cost note carries a one-line reason and goes to ApprAIsal, where it is reviewed with the costing; CompAIre no longer shows cost effects as findings |
| 17 Nov 2026 | Reviewer reading v1/v2 design | v1 compared the bill with one chosen bill only, so the "design options" were mostly near-copies of the bill (fake-distinct options) and the closest bill offered little to choose from | Failed | v3 picks a comparator per provision for its alternative (differences outweigh similarities), skips near-identical copies, and limits recommendations to four defined options |
| 17 Nov 2026 | Building the v3 rule draft | The rule draft first compared provisions with a Senate committee report that only repeats SB 1624's text, and described differences in garbled phrases ("members: 10 (this bill: 12)" in memo prose) | Failed | Committee reports dropped when the bill itself is available; separate table and memo phrasing ("SB No. 1345 ... provides for 10 members") |
| 17 Nov 2026 | Claude run on HB 9897 (fake-distinct options test) | The related bills (HB Nos. 6371, 4652, 2384, 1190 and SB No. 173) are largely copies of the same text | Held | CompAIre retained the provisions with no comparator ("no related measure offers a different design") instead of inventing differences, and used real alternatives only where they existed (SB No. 173's repealing clause, HB No. 4652's list of hazards) |


## ApprAIsal (Agent 3): Appraisal and Governance

Failure the course asks this agent to catch: drift toward tasks it should not do.

| Date | Test or how found | What happened | Result | Rule or fix |
|---|---|---|---|---|
| 8 Nov 2026 | Live run v1 on HB 2322 | Citations to explanatory notes failed the shared checker | Failed | Explanatory-note citations (`<id>:note`) added to the checker: 38/38 verified |
| 8 Nov 2026 | Red-teamer sub-agent (separate instance) | 14 issues (6 medium): factual slip on HB 11060's Technical Secretariat; SB 1624's status overstated ("now the Senate vehicle"); mandate difference overstated; comparisons between bills without their own citations; headcount and entity type not marked "to verify"; top of the cost range driven by obligations per filled position | Held (red-teamer recommended "revise first"; memo and letter not produced) | Prompt v2: comparisons need their own citations, status only as documented; costing engine v2: headcount anchored on authorized positions, judgement assumptions marked "to verify". AGRICOM range P28.9M–P545.2M → P67.0M–P424.2M |
| 8 Nov 2026 | Red-teamer | Could not check the comparator table because it was not in its input | Failed | Comparator table added to the red-team input |
| 16 Nov 2026 | Review of cost sources | COA obligations include program funds, overstating personnel cost per position | Failed | Method B moved to FY 2026 GAA personnel and overhead per authorized position; COA kept as a cross-check. HB 2322 P67.7M–P270.0M → P65.6M–P201.8M |
| 8 Nov 2026 | Scope test (governance) | Drafts must never state the DBM position or name officials | Held | Checker blocks forbidden phrases and officials' names; the letter opens only after the analyst sets the position |
| 17 Nov 2026 | Red-team: a peso figure not produced by the cost engine written into Part V | Flagged "figure not from the cost engine or the bill"; output not saved | Held | `appraise.check_output`; regression test `test_invented_peso_figure_is_flagged` |
| 17 Nov 2026 | Building v3 (memo compiled from the three agents) | The same sentence appeared in Part IV (CompAIre) and Part V (ApprAIsal) because their paragraph numbers differed, so the de-duplication missed it | Failed (caught before release) | `appraise.harmonize` compares sentences without their paragraph numbers and keeps the first part's number; test `test_harmonize_drops_repeated_sentences` |
| 17 Nov 2026 | Scope test (governance) | The overall recommendation could have gone straight into the memo from the agent | Held | ApprAIsal only proposes Part VII; the memo keeps a placeholder until the reviewer picks an option and confirms it; the letter opens only after that |
| 17 Nov 2026 | Claude run on HB 10648 (a subsidy program, not a new office) | The rule draft applied the new-office estimate (30 to 150 positions, P41.2 million to P210.5 million a year) to a cash subsidy program, and found no Budget and Management Bureau because the bill names the DSWD by its acronym | Failed (rules; caught before release) | New-office estimate only when the bill creates an office or body; the program's cost is described as benefits times coverage; agency acronyms counted when the bill defines them; DSWD matched to BMB-B |


## Portal and data (supporting the agents)

| Date | What happened | Fix |
|---|---|---|
| 16–17 Nov 2026 | The site went down (Streamlit memory limit, about 1 GB) because the FY 2027 General Appropriations Bill (25 MB of text) was loaded with the corpus | Long documents capped, lazy section loading, hashed similarity matrix; memory check before every daily update. Peak about 360 MB |
| 16 Nov 2026 | BILLy answered "I'm not sure" to its own quick button "What is ActCheck?" ("actcheck" was a stop word) | Exact-match and intent rules for the quick buttons |
| 16–17 Nov 2026 | Filing dates read from the House stamp by OCR broke filing order for 36 bills (e.g. HB 9430 read as May 28, stamped May 26) | Dates checked against filing order and corrected by visual check |
| 16 Nov 2026 | The daily check stopped finding new House bills after a gap in House numbering | Wider search for new numbers and catch-up of older bills |
