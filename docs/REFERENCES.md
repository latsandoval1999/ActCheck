# Government references used by ActCheck (added 16 Nov 2026)

All are public documents from the author's reference folder. The internal DBM position papers in that folder are
not read, used as model input, or stored in this repository.

| Reference | Where it is used | How |
|---|---|---|
| GAA FY 2026 by object (DBM) | `data/benchmarks/gaa_2026_by_agency.csv` (aggregate, `pipeline/gaa_aggregate.py`) | Cost estimate: MOOE share and Method B comparators |
| DBM Staffing Summary FY 2026 | `data/benchmarks/staffing_summary_2026.csv` | Authorized positions of comparators; checks the salary-grade assumption |
| DBM 2027 Budget Priorities Framework (expenditure priorities; macroeconomic and fiscal environment) | Library (`REF-BPF2027-EXP`, `REF-BPF2027-MACRO`), `pipeline/policy.py` | AppraisAI policy context; 2027 price note in the cost estimate |
| PSA Summary Inflation Report, October 2026 | Library (`REF-PSA-CPI-OCT2026`) | Price note in the cost estimate |
| LEDAC: 44 Common Legislative Agenda measures, 20th Congress (PCO, 30 Sept 2025) | `data/reference/ledac_cla_20th.csv`, Library (`REF-LEDAC-CLA20`) | "LEDAC priority" flag and filter on the Bills page; workspace notice; memo sentence; AppraisAI context |
| DICT-CSC JMC No. 003, s. 2026 (ethical and responsible AI in government) | How it Works, "Responsible AI" | Alignment table; added the "Report a problem with this output" mechanism (Sec. 6b) |
| NPC Advisory No. 2024-04 (DPA and AI systems); RA 10173 | How it Works, "Responsible AI" | Privacy, transparency and accountability rows |
| PIDS comment on the DWR bills (Navarro, 9 March 2026) | `eval/pids_hb6789.csv`, `eval/pids_eval.py` | Held-out benchmark for reviews of HB 6789; never given to the agents |
| COA annual audit reports (executive summaries) | `data/benchmarks/coa_comparators.csv` | Cross-check for the cost estimate |
| NBC No. 601 (2026 salary schedule) | `data/benchmarks/salary_schedule_2026.csv` | Personnel cost |
| DBM Citizen's Charter CY 2026 | How it Works | Process stages and times |

Available but not yet built in (candidates): CBO cost estimate primer and samples (format for presenting a cost
estimate), PIDS DP 2024-05 and DP 2023-04 (policy costing practice), OECD Principles for Independent Fiscal
Institutions, Rules of the House and Senate (status wording), Administrative Code (structure of departments, bureaus
and offices), DBM Manual on Position Classification (salary grades of new positions), Philippine Development Plan
2023-2028, Local Government Code, SB 1921 (Budgeting Code).
