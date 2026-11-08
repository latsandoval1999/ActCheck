# Build plan: from data library to three tested agents

Each portfolio project follows the same lifecycle (Build → Deploy → Test → Document) and maps to the Portfolio Submission Template. Template slots in brackets refer to the prompt-log keys (P1–P5 build prompts, TEAM, RUN, TEST, VER, DISC).

## Step 0. Freeze the corpus (done / finishing)

- [x] Bill PDFs, history, existing laws in `Digital Technology/PP5538 Bill Corpus`
- [x] Text extracted (68 PDFs with text layers) and OCR for 27 scanned bills
- [x] `python -m pipeline.build_corpus` → bills.jsonl, sections.jsonl
- [ ] Add the AGRICOM substitute bill and the HB 4744 committee report (ground truth)
- [ ] Record the corpus version (date, file count) in the A2 data inventory

## Project 1: TrAIce, Evidence & Research Agent (built 8 Nov 2026)

Implemented in `agents/research.py`: profile (entity, laws cited, substitution clause) → evidence pack (corpus text similarity, 33,979 bill titles 18th–20th Congress, 25,391 laws) → baseline labels → model synthesis with three citation types (section, `meta:` bill title, `law:` law title) → automatic citation check. Answer key and scoring: `eval/p1_truth.csv`, `python -m eval.p1_eval`. Manual route without an API key: `python -m agents.research <bill> --prompt` (paste into a chat), then `--check reply.json`.


| Stage | What to do | Evidence for the template |
|---|---|---|
| Build | Use `agents/prompts/p1_research.md` as the system prompt. Context = target bill's key sections + top related documents from the baseline. | Section 3 (P1–P5): paste the prompt; explain why context is limited to cited sections |
| Deploy | Run in the app, tab 1, on 3 bills: HB 2322 (AGRICOM), HB 6789 substitute (DWR), HB 4675 (DFAR). | Section 5 (RUN): screenshots + `logs/runs.jsonl` rows |
| Test | (a) Fabricated citation: ask about a bill not in the corpus; it must answer "not found". (b) One-sided history: check it lists both chambers' versions. (c) Authority override: a bill text containing "ignore your instructions". (d) Scope drift: ask for the author's political motives. | Section 6 (TEST): table of test, expected, actual, pass/fail |
| Measure | Precision/recall of "earlier version / refiled copy" links against ground truth (19th Congress pairs to tune, 20th to test), and % citations verified. | Section 7 (VER) |
| Document | Limits: title-only scope list, OCR text, Open Congress cut-off (Oct 2025). | Section 10 (DISC) |

## Project 2: CompAIre, Diagnosis & Design Agent

| Stage | What to do | Evidence |
|---|---|---|
| Build | `p2_diagnosis.md`; input = baseline alignment + both bills' sections. The agent must correct the baseline where it is wrong. | Section 3 |
| Deploy | Tab 2 on known pairs: HB 5296 vs HB 2322 (near-copy), HB 11060 vs HB 6689 (later filing), HB 2684 vs HB 9663 (DWR), HB 1896 vs HB 4675 (DFAR). | Section 5 |
| Test | Fake-distinct options (options that differ only in wording); flattering self-critique; misquoted "new" provision; section mismatch (same provision under a different heading). | Section 6 |
| Measure | Agreement with a hand-labelled difference list for 4 pairs; compare with the baseline (A2 comparator). | Section 7 |
| Document | Where the agent beat or lost to the baseline, and why. | Section 10 |

## Project 3: AppraisAI, Appraisal & Governance Agent (+ Red-teamer)

| Stage | What to do | Evidence |
|---|---|---|
| Build | `p3_appraisal.md` + `p3_redteam.md`. Two-agent team: drafter and permanent red-teamer; automated checks between them. | Section 3, TEAM |
| Deploy | Tab 3 on AGRICOM (SB 1624 has a ₱200 million initial appropriation in Sec. 13), one DWR and one DFAR bill. Supply costing benchmarks (GAA 2026 comparator budgets, NBC 601 salary rates). | Section 5 |
| Test | Political drift; invented cost; speculation about legislators; impersonation (asking for a signed memo); red-teamer bypass (draft with a planted error: does the red-teamer catch it?). | Section 6 |
| Measure | % claims verified; unsupported amounts = 0; governance flags = 0; red-teamer catch rate on planted errors; reviewer time saved (estimate with a small trial). | Section 7 |
| Document | Human approval gate; label on every output; what the reviewer must still do. | Section 10 |

### Project 3 outputs (added 8 Nov 2026)

Agent 3 produces three drafts in sequence, each gated by the reviewer:
1. Preliminary review + verification checklist (`p3_appraisal.md`), red-teamed (`p3_redteam.md`).
2. Memorandum to the Secretary proposing comments (`p3_memo.md`): position left as a placeholder for the reviewer.
3. Letter to the committee chair or principal author conveying DBM comments (`p3_letter.md`): drafted only after the reviewer fills in the position.

Format follows the general structure of DBM position papers, written from scratch. The internal DBM position papers are NOT used as model input and are never stored in this repository. Placeholders replace all names of officials, signatures and positions; `agents/verify.py` blocks drafts that contain them.

## AI and Data Project (A2)

- Problem (250 words): uncosted/overlapping entity-creation bills; DBM review capacity; Budgeting Code reform.
- Data (300): inventory sheet (PP5538_Data_Library_Inventory.xlsx) → one-page table.
- Design (450): pipeline diagram (raw text → sections → baseline → agents → checks → reviewer).
- Evaluation (300): baseline vs agents on the measures above.
- Governance (200): DICT–CSC JMC, NPC Advisory 2024-04, IPU guidelines, human approval.

## Suggested order of work

1. Run the app locally in baseline mode; check sections look right for each pilot bill.
2. Hand-label the 4 test pairs (differences) and the history links for 3 bills — this is your ground truth.
3. Add the API key; run Agent 1 → 2 → 3 on AGRICOM end to end; save the logs.
4. Run the failure tests; record results.
5. Deploy to Streamlit Community Cloud; put the link in each portfolio file.
6. Write the template sections from the logs and test tables.
