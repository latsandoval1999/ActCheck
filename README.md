# ActCheck

*Checking bills before they become Acts.* A student prototype for PP5538, not an official DBM system.

| Agent | Portfolio project | Role |
|---|---|---|
| **TrAIce** | P1 Evidence & Research | Daily check for new bills; traces earlier and parallel versions and related laws |
| **CompAIre** | P2 Diagnosis & Design | Compares the bill with related measures; problem, differences, design options |
| **AppraisAI** | P3 Appraisal & Governance | Cost range, risks, preliminary comments, memo and letter drafts (with a red-teamer) |

A reviewer portal that lists **every House and Senate bill** and helps staff of the DBM Budget Information Legislative and Liaison Service (BILLS) do their **preliminary review**. The agents are being tested first on the **pilot scope: bills that create a new national government agency** (all sectors); other bills with full text can be reviewed experimentally.

Live portal: https://act-check.streamlit.app Built for the PP5538 Agentic AI Portfolio (three projects) and the AI and Data Project.

> Every output is an **AI-assisted preliminary draft for DBM reviewer validation**. The portal never states a DBM position, signs anything, or replaces the reviewer.

## How the portal works

1. **Daily check (TrAIce, monitoring).** Every morning a scheduled GitHub job (`.github/workflows/daily-watch.yml` → `pipeline/watch.py`) refreshes the bill list from Open Congress Data, looks for newly filed House bills (House documents server) and Senate bills (the Senate website's public listing), reads them (OCR if scanned), tags the pilot-scope ones and lists them all on **Home** and **Bills**. Optionally TrAIce drafts an evidence brief for each new pilot-scope bill.
2. **Open a bill → Run full review.** One click runs TrAIce (history, earlier and parallel versions in both chambers, existing laws), CompAIre (problem, substantial differences vs the closest related measure, design options) and AppraisAI (preliminary review, cost range, risks, preliminary comments), then the red-teamer.
3. **Reviewer works through the tabs**: Evidence · Comparison · Appraisal (approve) · Comments & report (edit comments, download Word/Markdown report) · Memo & letter (memo after approval; letter after the reviewer decides the position).
4. **Ask about this bill**: a chat that answers only from the bill's workspace and cites sections (citations are checked).

Without an API key, every rules-only part still works and each agent step offers a **free route**: download the prompt, run it in a Claude chat, paste the reply back to check and save it.

## What it does

| Part | Portfolio project | What it does | Safeguard |
|---|---|---|---|
| TrAIce | P1 Evidence & Research | Finds earlier versions, refiled copies, counterpart bills and existing laws related to a bill | Each link must cite and quote a section; quotes are checked automatically |
| CompAIre | P2 Diagnosis & Design | Compares the bill with a related measure, lists substantial differences and their fiscal direction, corrects the baseline alignment | Both versions quoted; non-AI alignment shown beside the agent's |
| AppraisAI + Red-teamer | P3 Appraisal & Governance | Drafts a preliminary report with a cost range (only from sourced assumptions) and a verification checklist; a second agent red-teams it | Checks for unsupported amounts, unverified quotes, official positions or signatures |
| Baseline | A2 comparator | TF-IDF similarity and section alignment, no AI | Reproducible benchmark the agents must beat |

## Try each agent without an API key (free route)

```bash
python3 -m agents.research  HB-20-2322 --prompt > p1.txt                 # TrAIce
python3 -m agents.diagnosis HB-20-2322 SB-20-1624 --prompt > p2.txt      # CompAIre
python3 -m agents.appraisal HB-20-2322 --step review --prompt > p3.txt   # AppraisAI (then redteam, memo, letter)
```
Attach the file to a Claude chat, ask it to follow the SYSTEM PROMPT and reply with JSON only, copy the reply, then `pbpaste > reply.json` and run the same command with `--check reply.json` instead of `--prompt`. Results are saved to `logs/` for the run log and scoring (`python3 -m eval.p1_eval --runs logs/p1_runs.jsonl`, `python3 -m eval.p2_eval --runs logs/p2_runs.jsonl`).

## Repository layout

```
app/streamlit_app.py        web app (baseline mode without a key; agents with a key)
agents/prompts/*.md         system prompts for the agents (portfolio template, Section 3)
agents/pipeline_agents.py   context building, model calls, checks
agents/verify.py            citation, amount and governance checks (no AI)
agents/llm.py               Anthropic API wrapper; logs every run to logs/runs.jsonl
pipeline/build_corpus.py    raw text -> data/processed/bills.jsonl, sections.jsonl
pipeline/sections.py        splits bills into sections (handles Senate line numbers, OCR quirks)
pipeline/extract.py         rule-based facts: amounts, salary grades, members, funding source
pipeline/compare.py         non-AI baseline: related bills and section alignment
data/raw_text/              text of each bill/law (pdftotext or OCR)
data/processed/             generated corpus + catalogue CSVs
tests/test_checks.py        failure tests that run without an API key
```

## Run it on your computer

```bash
python -m venv .venv && source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python -m pipeline.build_corpus                         # rebuild data/processed from data/raw_text
pytest -q                                               # failure tests (no key needed)
streamlit run app/streamlit_app.py                      # opens http://localhost:8501
```

For live agents, either paste an Anthropic API key in the app's sidebar (kept for that session only) or create `.streamlit/secrets.toml` with `ANTHROPIC_API_KEY = "..."` (this file is git-ignored; never commit a key).

## Download more bills (run on your own computer)

`pipeline/fetch_bills.py` downloads bill PDFs for any of the 218 entity-creation families listed in `data/processed/family_bills.csv` (1,672 bills, 18th–20th Congress). It uses only Python's standard library, so nothing needs installing.

```bash
cd "~/Desktop/Digital Technology/bill-review-agents"
python3 -m pipeline.fetch_bills --list-families                 # family IDs and sizes
python3 -m pipeline.fetch_bills --family F002 --dry-run          # preview
python3 -m pipeline.fetch_bills --family F002 F013 --congress 20 # download
```

Files go to `PP5538 Bill Corpus/6 Downloads/<family>/<Congress>/`. Bills already in the corpus are skipped, reruns resume where they stopped, and every attempt is logged in `download_log.csv`. The script waits 4 seconds between requests and respects robots.txt; keep those settings.

## Daily watcher

```bash
python3 -m pipeline.watch --dry-run                    # what would be checked
python3 -m pipeline.watch --chamber HB --max-probe 5   # a small real check (run on your own computer)
python3 -m pipeline.build_corpus                       # add what it found to the corpus
```
- **House:** checks the House documents server for the next bill numbers (up to 60 a day). The congress.gov.ph listing pages use a bot challenge, which the watcher does not bypass.
- **Senate:** reads the public listing behind senate.gov.ph/legislative-documents/bills (`/lis/documents_v2`, allowed by robots.txt) and saves every 20th Congress Senate bill to `data/processed/senate_listing_20.csv`; then downloads up to 25 bill texts a day from each bill's record (pilot-scope bills first).
- **Bill list:** `pipeline/catalogue.py` merges Open Congress Data, the Senate listing, the daily check and the corpus into the list shown on the Bills page.
- A failed check is reported as "source unavailable", never as "no new bills". Add an `ANTHROPIC_API_KEY` repository secret to let TrAIce triage new pilot-scope bills automatically.

## Put it online (testable link)

1. Create a GitHub repository and push this folder (see "Push to GitHub" below).
2. Go to share.streamlit.io, sign in with GitHub, choose **New app**, pick the repository, branch `main`, file `app/streamlit_app.py`.
3. Optional: under **Advanced settings → Secrets**, add `ANTHROPIC_API_KEY = "..."` so visitors can run the agents on your key. Leave it out to make visitors paste their own key (safer for your budget).
4. Streamlit gives you a public URL to share with your professor.

### Push to GitHub

```bash
git init && git add . && git commit -m "Initial prototype"
git branch -M main
git remote add origin https://github.com/<your-username>/<repo-name>.git
git push -u origin main
```

## Data and licences

| Source | Used for | Licence / terms |
|---|---|---|
| House of Representatives and Senate bill PDFs (20th and 19th Congress) | Bill texts | Public government documents |
| Open Congress Data, BetterGov.PH (github.com/bettergovph/open-congress-data, commit 6e853ee) | Bill metadata, scope catalogue | CC0 1.0 |
| Philippine Legal Documents Library, BetterGov.PH (data.bettergov.ph/datasets/24), from Lawphil | Existing-law texts | CC BY-NC 4.0 (non-commercial, attribution) |

Text from 27 scanned bills was produced by OCR (Tesseract) and is flagged `text_source: ocr`; quotes from those bills must be checked against the PDF. No personal data beyond legislators' names as printed on public bills is processed. Do not add internal or restricted government documents to this repository.

## Status and limits

- Pilot families: Congressional Commission on Agriculture (AGRICOM), Department of Water Resources, Department of Fisheries and Aquatic Resources. Scope catalogue covers 218 entity-creation families (18th–20th Congress), auto-extracted from titles and still to be reviewed.
- Baseline thresholds (`pipeline/compare.py`) are untuned: tune on 19th Congress pairs, test on 20th.
- Costing needs benchmarks (GAA 2026, staffing summary, salary schedule). Without them AppraisAI must answer "cannot estimate".
- Model is set in `agents/llm.py` (`BILL_AGENT_MODEL` environment variable overrides it).
