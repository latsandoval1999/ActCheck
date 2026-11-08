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
