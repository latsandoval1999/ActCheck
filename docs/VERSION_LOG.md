# Version log (for the portfolio template)

Each live run is archived in `runs_archive/` (prompt sent + reply received) and logged in `logs/*.jsonl`.
"Live run" here = the agent's prompt executed by a separate Claude instance that saw only the prompt file (no conversation history, no answer key), equivalent to an API call.

## TrAIce (Agent 1): Evidence & Research

| Version | Date | Change | Why | Result on HB 2322 |
|---|---|---|---|---|
| v1 | 8 Nov 2026 | First build: profile → evidence pack (corpus text, 33,979 bill titles, 25,391 law titles) → model labels with citations → automatic citation check | — | 11/11 citations verified; 3/3 answer-key relations correct. Gaps the agent itself reported: committee report's chamber unknown; RA 11899 forced into "unrelated"; HB 11060 listed by the baseline but its text missing from the pack |
| v2 | 8 Nov 2026 | (a) new label "precedent or model"; (b) front matter of committee reports and substitutes added and citable as `<id>:note`; (c) up to 8 related bills with key sections, the rest with their short-title section; (d) sections that cite existing laws always included | Fix the three gaps v1 reported | 12/12 citations verified; committee report correctly read as the Senate report recommending SB 1624; RA 11899 and SB 2485 (18th) labelled "precedent or model"; HB 11060 now assessed ("competing design") |

Open issues: baseline label "same subject (competing or related design)" is not one of the agent's labels (the agent flagged this); House substitutes do not list the bills they replace (needs House committee reports).

## CompAIre (Agent 2): Diagnosis & Design

| Version | Date | Change |
|---|---|---|
| v1 | 8 Nov 2026 | Problem diagnosis (explanatory notes, citable as `<id>:note`), substantial differences with fiscal direction, design options from family variants, baseline corrections. Context sends full text only for sections that differ; identical sections listed by ID. Checks: citations, labels, differences claimed in near-identical sections. |

Live run v1, HB 2322 vs SB 1624 (Senate substitute): verdict "partly different"; 29/29 citations verified; 0 flags; 10 differences (members 12 vs 10, P200,000,000 fixed initial funding vs "amount necessary", PIDS research arm only in HB 2322, national-assessment scope only in SB 1624, GAA deficiency clause only in HB 2322, etc.); 6 design options; 10 baseline corrections (e.g. Duration, Advisory Council and Technical Secretariat clauses marked "changed" by the baseline but equal in substance; Effectivity mis-paired with Repealing clause because of OCR).
Reviewer note (to test in v2): one fiscal direction looks wrong. The agent labelled SB 1624's added operational tasks (training programs for farmers, identifying markets) "likely lowers cost"; added tasks should normally raise cost. Candidate fix: require a one-line reason for each fiscal direction and have the red-teamer check them.

## AppraisAI (Agent 3): Appraisal & Governance

| Version | Date | Change |
|---|---|---|
| v1 | 8 Nov 2026 | Four gated steps: review → red-team → memo (position placeholder) → letter (only after the reviewer fills the position). Costing engine does all arithmetic (2026 salary schedule from NBC 601; mandatory benefits; COA comparators matched by entity type); the model may only quote engine or bill figures. Checks: citations, unsupported peso figures, forbidden phrases, officials' names, label and placeholders. |

Live run v1, HB 2322 (with Agent 1 v2 and Agent 2 v1 outputs as inputs): 38/38 citations verified (after adding explanatory-note citations to the shared checker); 0 unsupported peso figures; 0 governance flags; 14 checklist items.
Red-teamer (separate instance): 14 issues (0 high, 6 medium, 8 low); recommendation "revise first". Medium issues: factual slip on HB 11060's Technical Secretariat; SB 1624's status overstated ("now the Senate vehicle"); mandate difference overstated (HB 2322 s3(b) also targets global competitiveness); comparisons between bills lacked their own citations; headcount and entity type not flagged "to verify"; top of the range driven by total obligations / filled positions.

| Version | Date | Change after red-team | Effect |
|---|---|---|---|
| Costing engine v2 | 8 Nov 2026 | Commission headcount anchored on comparators' authorized plantilla (76-124, was 30-130); per-staff benchmark divides by authorized positions, not filled; every judgement assumption marked to_verify; Method B labelled an upper bound | AGRICOM range P67.0M-P424.2M (was P28.9M-P545.2M) |
| Agent 3 prompt v2 | 8 Nov 2026 | Comparisons between bills need their own citations; status only as documented; upper-bound note | To be tested in the next run |
| Red-team input v2 | 8 Nov 2026 | Comparator table included (red-teamer could not check it in v1) | To be tested in the next run |

Human gate: the memo and letter steps were NOT run, because the red-teamer recommended revision and the reviewer has not approved the review. This is the intended behaviour.

## Naming (8 Nov 2026)
Portal renamed ActCheck; agents renamed TrAIce (P1), CompAIre (P2) and AppraisAI (P3). Prompts now open with the agent's name; no change to rules or checks.

## Scope and portal v2 (8 Nov 2026)
Scope widened: the portal lists every House and Senate bill (Open Congress Data + Senate website listing + daily check); agents remain tested on the pilot scope (bills creating a national agency). Senate route moved to the new senate.gov.ph listing feed. Portal redesigned (Home, Bills, Review workspace, Ask ActCheck, Library, Run log, About) with a prototype notice on every page.

## Portal v3 (8 Nov 2026), from the author's edit list
BantAI-style redesign (navy, gold, red; hero photo with on-screen images replaced; scale-and-check logo); footer credit; homepage summary, typology chart and workflow; Bills tab with Type and Status filters, clickable titles, View bill and Review; on-demand text fetch; review workspace with queue, sequential steps, gating checklists with notes and uploads, concise outputs; DBM-format memo and letter (Tahoma, fields pre-filled from the approved review; AppraisAI memo/letter prompts now return template fields); BILLy companion (search mode without a key); How it Works tab with the Citizen's Charter process.


## 16 Nov 2026: new government references built in

| Area | Change | Why |
|---|---|---|
| Cost estimate (AppraisAI) | Method B now uses FY 2026 GAA Personnel Services plus overhead MOOE per authorized position (DBM Staffing Summary FY 2026); MOOE share set to 31%-64% from 9 comparators; COA figures kept as a cross-check; 2027 price note (BPF inflation 4-5%) | COA obligations include program funds; the open items in docs/COSTING_CHECK.md needed current budget data |
| Policy context (AppraisAI, memo, portal) | LEDAC Common Legislative Agenda flag and filter (535 of 6,120 20th Congress bills related by title); 2027 BPF priority areas and fiscal stance as citable Library references; memo sentence for LEDAC measures; new `policy_context` field in the AppraisAI draft | DBM reviewers weigh priority status and fiscal space; facts are cited and checked like bill sections |
| Governance | "Report a problem with this output" on every step (logged to the bill and the Run log); How it Works maps safeguards to DICT-CSC JMC No. 003 s. 2026 and NPC Advisory 2024-04 | JMC Sec. 6(b) requires a reporting and feedback mechanism and disclosure |
| Evaluation | PIDS comment on the DWR bills (9 March 2026) as a held-out benchmark for HB 6789 (10 points, 9 relevant to HB 6789); `python -m eval.pids_eval`; a test keeps it out of agent inputs | Independent expert comparison for the testing section |

Effect on cost ranges: HB 2322 P67.7M-P270.0M -> P65.6M-P201.8M; HB 6789 P359.9M-P3.78B -> P448.5M-P3.08B.
