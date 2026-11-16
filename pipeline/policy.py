"""Policy context for a bill: LEDAC priority status and the DBM fiscal priorities for 2027.

Sources (public, in data/reference/):
  ledac_cla_20th.csv              the 44 Common Legislative Agenda measures of the 20th Congress (LEDAC,
                                  30 September 2025), each with a title pattern for matching bills
  docs/REF-BPF2027-*.json         DBM briefers on the 2027 Budget Priorities Framework
  docs/REF-PSA-CPI-OCT2026.json   PSA inflation report, October 2026

Matching is on the bill's title, so a match means "related to a LEDAC measure by title"; the analyst confirms.
"""
import csv
import json
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
REF = ROOT / "data" / "reference"
LEDAC_URL = "https://pco.gov.ph/news_releases/pbbm-congress-firm-up-44-common-legislative-agenda-measures-for-20th-congress/"

# 2027 BPF priority areas (REF-BPF2027-EXP sections) and title keywords that point to them
BPF_AREAS = [
    ("Human capital development", 2, r"EDUCATION|SCHOOL|TEACHER|STUDENT|SCHOLAR|HEALTH|HOSPITAL|MEDICAL|NUTRITION|SOCIAL WELFARE|SOCIAL PROTECTION|\bLABOR\b|EMPLOYMENT|WORKERS"),
    ("Food security", 3, r"AGRICULTUR|\bFARM|FISHER|AQUATIC|\bFOOD\b|\bRICE\b|COCONUT|LIVESTOCK|IRRIGATION"),
    ("Infrastructure development", 4, r"INFRASTRUCTURE|\bROADS?\b|BRIDGE|RAILWAY|AIRPORT|SEAPORT|PUBLIC WORKS|TRANSPORT"),
    ("Digitalization", 5, r"DIGITAL|INFORMATION AND COMMUNICATIONS|E-GOVERNMENT|INTERNET|CYBER|ONLINE"),
    ("Environment, climate, and disaster resilience", 6, r"ENVIRONMENT|CLIMATE|DISASTER|WATER RESOURCES|FOREST|COASTAL|MARINE|WEATHER|RESILIEN|EMERGENCY"),
    ("Implementation of full devolution to LGUs", 7, r"LOCAL GOVERNMENT|BARANGAY|DEVOLUTION"),
]


@lru_cache(maxsize=1)
def _ledac():
    with open(REF / "ledac_cla_20th.csv", newline="") as f:
        return [(int(r["no"]), r["measure"], re.compile(r["title_pattern"], re.I)) for r in csv.DictReader(f)]


def ledac(title, congress="20"):
    """LEDAC measures a 20th Congress bill relates to by title: [(no, measure), ...]."""
    if str(congress) != "20" or not title:
        return []
    return [(n, m) for n, m, p in _ledac() if p.search(title)]


@lru_cache(maxsize=None)
def reference(doc_id):
    p = REF / "docs" / f"{doc_id}.json"
    return json.loads(p.read_text()) if p.exists() else None


def context(bill):
    """Facts for the agents and the memo: LEDAC status, matching 2027 budget priority, fiscal stance.
    `bill` is a dict with title and congress."""
    out = {"ledac": [{"no": n, "measure": m, "source": "REF-LEDAC-CLA20:s2"} for n, m in ledac(bill.get("title", ""), bill.get("congress"))]}
    out["bpf_2027_priority_areas"] = [{"area": a, "source": f"REF-BPF2027-EXP:s{n}"} for a, n, rx in BPF_AREAS
                                      if re.search(rx, bill.get("title", ""), re.I)]
    out["fiscal_stance"] = [
        {"point": "FY 2027: programs and projects to be rationalized to eliminate redundancies and enhance allocative efficiency", "source": "REF-BPF2027-EXP:s1"},
        {"point": "Proposed FY 2027 budget of Php 7.2 trillion (21.7% of GDP); deficit to narrow from 5.4% of GDP in 2026 to 3.5% by 2030", "source": "REF-BPF2027-MACRO:s1, REF-BPF2027-MACRO:s4"},
        {"point": "Inflation assumption 4.0-5.0% for 2027 after 6.0-7.0% in 2026; headline inflation 7.8% in October 2026", "source": "REF-BPF2027-MACRO:s2, REF-PSA-CPI-OCT2026:s1"},
    ]
    return out


def memo_line(bill):
    """One factual sentence for the DBM memo when the bill relates to a LEDAC measure."""
    hits = ledac(bill.get("title", ""), bill.get("congress"))
    if not hits:
        return ""
    n, m = hits[0]
    return (f" The measure relates to item {n} ({m}) of the 44 Common Legislative Agenda measures of the 20th Congress "
            "identified by the LEDAC on 30 September 2025.")
