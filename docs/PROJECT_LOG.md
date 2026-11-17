# Agentic AI Portfolio and Project Log

Major versions of ActCheck, with what was added, revised or removed for the agents and the portal, and the effect
measured on the test bills (HB 2322, AGRICOM; HB 6789, Department of Water Resources). The detailed change record
for the portfolio template is in `docs/VERSION_LOG.md`.

## Version 1 · 8 November 2026 · First working prototype

### Agents
| | What | Effect |
|---|---|---|
| Added | **TrAIce** (evidence and research): profiles the bill, gathers earlier versions, counterpart and refiled bills and related laws, labels each relation and quotes a section for it; every quote is checked against the text | HB 2322: 11 of 11 quotes verified; 3 of 3 answer-key relations correct |
| Revised | TrAIce v2: new label "precedent or model"; committee-report front matter citable; up to 8 related bills with their key sections | Fixed the three gaps TrAIce itself reported; 12 of 12 quotes verified; the Senate committee report read correctly |
| Added | **CompAIre** (diagnosis and design): the problem the bill addresses, substantial differences with the closest bill and their likely effect on cost, design options | HB 2322 vs SB 1624: 29 of 29 quotes verified; 10 differences; 6 design options |
| Added | **ApprAIsal** with a second AI reviewer (red-teamer): a fixed calculator does all arithmetic (2026 salary schedule, NBC No. 601; COA comparators) and the model may only quote its figures; steps gated review → second review → memo → letter | 38 of 38 quotes verified; 0 unsupported peso figures; the second reviewer found 14 issues and advised "revise first", so the memo was held for the analyst (the intended human gate) |
| Revised | Cost calculator v2: headcount anchored on comparators' authorized positions; every judgement assumption marked "to verify" | AGRICOM range narrowed from P28.9M-P545.2M to P67.0M-P424.2M |
| Renamed | Portal **ActCheck**; agents TrAIce, CompAIre and ApprAIsal | Names used in prompts, outputs and the portal |

### Portal
| | What |
|---|---|
| Added | Home, Bills (every House and Senate bill of the 18th-20th Congress), Review workspace with step-by-step checklists that unlock the next step, Library, Run log, How it Works, BILLy companion |
| Added | DBM-format memorandum and letter (Word download), filled from the approved review |
| Revised | Scope widened from a pilot list to all bills; the agents stay tested on bills that create a government agency |

## Version 2 · 16 November 2026 · Government references, daily monitoring and a public view

### Agents
| | What | Effect |
|---|---|---|
| Revised | **ApprAIsal cost estimate**: Method B uses the FY 2026 GAA (personnel and overhead per authorized position, DBM Staffing Summary FY 2026); COA figures kept as a cross-check; 2027 price note from the Budget Priorities Framework | HB 2322: P67.7M-P270.0M → P65.6M-P201.8M; HB 6789: P359.9M-P3.78B → P448.5M-P3.08B |
| Added | **Policy context** for ApprAIsal and the memo: LEDAC Common Legislative Agenda flag and 2027 budget priority areas, quoted and checked like bill sections | 535 of 6,120 20th Congress bills flagged as related to a LEDAC priority |
| Revised | **Memo and letter** follow the DBM position-paper format (letterhead text, standard closing lines); no officials' names; the letter opens only after the analyst sets the position | Drafts ready for the analyst to finalize; the position stays the analyst's decision |
| Added | **Safeguards**: "Report a problem" on every step; safeguards mapped to DICT-CSC JMC No. 003 s. 2026 and NPC Advisory No. 2024-04 | Feedback and disclosure required by the JMC are in place |
| Added | **Evaluation**: the PIDS comment on the water resources bills used as an independent benchmark for HB 6789 | An expert comparison for the testing section |
| Revised | **Daily check** (TrAIce's monitoring): wider search for new House bill numbers, catch-up of older bills, a check of every data source, 9:00 AM Manila schedule; Senate list refreshed weekly | New bills found again after a gap in House numbering had stopped the check |

### Portal
| | What |
|---|---|
| Added | Public view, with a reviewer Log In button (no password, for this course prototype) |
| Added | Bill status in four groups (pending, enacted, consolidated or substituted, not enacted), filled from Republic Act records; filing date and principal author |
| Added | Public Report button, with a notice in the part of the Review workspace each report concerns |
| Revised | How it Works: the DBM Citizen's Charter stages (39 working days, about 25 with ActCheck, illustrative) and the agents with their safeguards; Library split into Review References and Full Text of Bills |

### Fixes on 17 November 2026
| | What | Effect |
|---|---|---|
| Revised | Memory: very long documents shortened (the FY 2027 General Appropriations Bill alone was 25 MB of text); bill text read only when needed; leaner bill comparison; a memory check before every daily update | Peak memory from about 1 GB (the site was restricted) to about 360 MB |
| Added | Filing dates read from the House receiving stamp and checked against filing order | Dates for bills whose list entry had none |
| Revised | TrAIce redesigned (version 3): policy context first (what the bill proposes; alignment with the FY 2027 Budget Priorities Framework, the LEDAC agenda and, for government organization bills, the Government Optimization Act, RA No. 12231); legislative history; Related Bills grouped by plainer relationship labels; Related Laws; fiscal requirements; memo-ready Parts II and III that the reviewer can edit | TrAIce's output becomes the first part of the memo; works without an API key (draft made by code) |
| Revised | Evidence quotes kept in the background (still checked); sections cited as "Section N (Section Title)"; one Notes and attachments box per checklist; 'Report a problem' and the copy-and-paste chat route removed from Step 1 | Shorter, cleaner review step |
| Fixed | Red-team test: a quote with an altered amount (P50 million instead of the P20 million in RA No. 8435, Section 116) passed the fuzzy quote check as "verified". Figures in a quote must now match the source exactly | Fabricated or altered figures are flagged "quote not found in section" |
| Added | Proofreading check by code (scripts/proofread.py, run daily): possible misspellings, repeated words, a/an, numbers in words that differ from the figure, skipped section numbers; findings appear under TrAIce's "For checking" item | 859 findings across 671 bills on first run |
| Revised | TrAIce: unrelated bills no longer listed; fiscal requirements moved to the ApprAIsal step; salient features as a lettered list of the major sections; checklist reduced to two items; fixed progress bar and a remove button for bills in the Review workspace | |
| Added | Overall evidence grade for each TrAIce output (A Strong to D Weak, 8 points: how the bill text was read, preparation and citation checks, full-text share of the related-measure map, points left to confirm), shown under the final checklist item; rule drafts capped at B | Grading done by code, not by the agent |
| Added | Scheduled TrAIce runs by Claude under the owner's subscription (scripts/traice_batch.py): workspace bills first, then the 422 Government organization and mandates bills with full text; nothing is saved unless every citation is verified | No API key needed |
| Added | docs/FAILURES_LOG.md: real failures found and fixed, by agent, for the portfolio templates | |
| Revised | CompAIre redesigned (version 3): what the bill aims to address; Substantial Differences and Design Options table (section or area, related measure chosen per provision for its alternative, major differences, recommended option with reason, trade-offs, gaps); memo Part IV (Comments and Recommendations) only for provisions needing a decision; duplications and cost effects passed to ApprAIsal; one checklist item with the evidence grade; Claude's verified run for HB 2322 (13 of 13 citations) | CompAIre answers "what is materially different, is it a valid design, and should it borrow from related bills" |
| Revised | Evidence grade shared by the agents (agents/grading.py); the note shows the grade, points and what to note, the method moved to How it Works; review progress shown only in the left rail with the agents' names; template-only bills and laws dropped from TrAIce; "(if needed)" on the optional edit and notes boxes; Bills table and page buttons evenly spaced | |
| Revised | ApprAIsal redesigned (version 3, renamed from AppraisAL): fiscal and budgetary requirements per provision (existing requirement in the bill, budgetary considerations from DBM costing references, recommendation on budgetary capacity and the GAA, risks); PS, MOOE and CO estimate computed by code from DBM costing parameters (memo Part V); possible duplication with existing agencies assessed under RA No. 12231 when the bill does not abolish or merge them (Part VI); proposed overall recommendation from the three DBM options (Part VII), confirmed by the reviewer; DBM bureaus and offices to refer the bill to, from the CY 2026 DBM Charter functional statements; bureau comments pasted in without a separate sign-in | HB 2322: P107.1M–P196.8M first-year requirement; memo now numbered I to VII and harmonized so no part repeats another |
| Revised | Review steps reduced to four (TrAIce, CompAIre, ApprAIsal, Memo and letter); the separate comments step removed; memo shown first with an Edit memo button | |
| Added | DBM bureau coverage (data/reference/dbm_bureau_coverage.json, from the DBM Central Office Directory; office e-mail addresses only, no officials' names): ApprAIsal now names the Budget and Management Bureau (A to F) or LGRCB from the agencies the bill names, ranked by the agency whose budget is charged, the agency the new office is attached to, then agencies given a role; each bureau request shows the office e-mail address; a referral to a bureau with no covered agency in the bill is flagged | HB 2322 → BMB-C (Congress; PIDS as research arm) |
