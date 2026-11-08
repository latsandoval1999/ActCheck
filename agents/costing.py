"""Deterministic first-year cost range for a bill that creates a government entity.

The AI never does arithmetic. Agent 3 narrates the numbers produced here, and the
verifier rejects any peso figure in its draft that this engine (or the bill) did not produce.

Two methods, reported side by side:
  A. Bottom-up personnel cost: head of agency at the salary grade the bill sets (if any)
     + staff (low/high headcount) at an assumed average salary grade, loaded with
     mandatory benefits; plus maintenance and other operating expenses (MOOE) as a
     share of personnel cost.
  B. Top-down comparator: all-in obligations per staff member of comparable agencies
     (COA audit reports) x the same headcount range.
The range is the min and max across both methods. If the bill states an amount, it is
shown as the bill's own figure, not replaced.

Every assumption carries a source; those marked "to verify" must be confirmed by the
reviewer before the figure is used.
"""
import csv
import re
from pathlib import Path

from pipeline.compare import load

ROOT = Path(__file__).resolve().parents[1]
BENCH = ROOT / "data" / "benchmarks"

# Mandatory benefits on top of basic salary (annual). Rates as commonly applied in the
# national government; each must be confirmed against current DBM issuances.
BENEFITS = [
    ("Year-end bonus (one month basic)", "months", 1.0, "RA 11466; paid with the first November payroll"),
    ("Mid-year bonus (one month basic)", "months", 1.0, "RA 11466 / EO 201 s. 2016; paid from May 15"),
    ("GSIS retirement and life insurance, government share 12% of basic", "pct", 0.12, "RA 8291, Sec. 5"),
    ("PhilHealth, government share 2.5% of basic (half of 5%), capped at P2,500 a month", "philhealth", 0.025,
     "RA 11223; DBM Circular Letter 2024-3 (5% shared equally, floor P10,000, ceiling P100,000)"),
    ("PERA, P2,000 per month", "fixed_monthly", 2000, "DBM rules on PERA (unchanged in 2026)"),
    ("Pag-IBIG government share, P200 per month", "fixed_monthly", 200, "2% of the P10,000 maximum fund salary (HDMF, 2024) (to verify)"),
    ("ECC, P100 per month", "fixed_monthly", 100, "PD 626 as amended; GSIS Resolution No. 9 s. 2003 (raised from P30 to P100)"),
    ("Clothing/uniform allowance, P7,000 per year", "fixed_annual", 7000, "DBM-COA rules on uniform/clothing allowance"),
    ("Cash gift, P5,000 per year", "fixed_annual", 5000, "RA 11466 (with the year-end bonus)"),
    ("Productivity enhancement incentive, P5,000 per year", "fixed_annual", 5000, "DBM Circular Letter 2025-13 under BC 2017-4 (needs yearly authority)"),
    ("Medical allowance, up to P7,000 per year", "fixed_annual", 7000, "EO 64 s. 2024; DBM Budget Circular 2024-6 (from FY 2025)"),
]
# Not included because they are discretionary or position-specific: Service Recognition Incentive (P20,000 when
# authorized by an Administrative Order), RATA for officials, hazard pay, overtime, loyalty and anniversary awards.

# Default headcount ranges by entity type, anchored on comparators in coa_comparators.csv.
STAFF_DEFAULTS = {
    "department": (552, 1728, "DHSUD had 552 personnel in its first full year (COA 2020); DMW had 1,728 approved positions in 2023 (COA 2023) (to verify)"),
    "authority": (100, 400, "NWRB has 124 plantilla positions (COA 2025); reviewer to adjust for mandate"),
    "commission": (76, 124, "Authorized plantilla of comparators: Climate Change Commission 76, NWRB 124 (COA 2025); the bill itself sets no staffing (to verify)"),
    "bureau": (100, 300, "Reviewer to set; no bureau-level comparator yet in the benchmark table"),
    "council": (15, 60, "Reviewer to set; small secretariat assumed"),
    "office": (30, 150, "Reviewer to set"),
}
# Comparators matched to entity type (program-heavy agencies like BFAR or OCD are excluded
# from per-staff benchmarks because their obligations include large program funds).
COMPARATOR_DEFAULTS = {
    "department": ["Department of Human Settlements and Urban Development", "Department of Migrant Workers"],
    "authority": ["National Water Resources Board", "Cooperative Development Authority"],
    "commission": ["Climate Change Commission", "National Water Resources Board"],
    "bureau": ["Cooperative Development Authority", "National Water Resources Board"],
    "council": ["Climate Change Commission"],
    "office": ["Climate Change Commission", "National Water Resources Board"],
}
MOOE_SHARE = (0.35, 0.60, "MOOE as a share of personnel cost; reviewer to confirm from GAA 2026 lines of comparator agencies")
AVG_STAFF_SG = (13, 18, "Assumed average salary grade of staff (Step 1); reviewer to confirm against a draft staffing pattern")


def salary_schedule():
    out = {}
    with open(BENCH / "salary_schedule_2026.csv") as f:
        for r in csv.DictReader(f):
            out[int(r["salary_grade"])] = int(r["step_1"])
    return out


def comparators():
    with open(BENCH / "coa_comparators.csv") as f:
        return list(csv.DictReader(f))


def annual_cost_per_person(monthly_basic):
    """Basic salary x 12 plus mandatory benefits, using BENEFITS."""
    annual = monthly_basic * 12
    total = annual
    for _, kind, v, _ in BENEFITS:
        total += {"months": monthly_basic * v, "pct": annual * v, "fixed_monthly": v * 12, "fixed_annual": v,
                  "philhealth": min(max(monthly_basic, 10000), 100000) * v * 12}[kind]
    return total


def entity_type(bid):
    bills, _ = load()
    t = bills[bid]["title"].upper()
    for k in ("DEPARTMENT", "AUTHORITY", "COMMISSION", "BUREAU", "COUNCIL", "OFFICE"):
        if re.search(r"(CREATING|ESTABLISHING|CREATION OF|ESTABLISHMENT OF)[^,]{0,60}?\b" + k, t):
            return k.lower()
    return "office"


def cost_range(bid, staff=None, avg_sg=None, mooe=None, comparator_names=None):
    bills, _ = load()
    b = bills[bid]
    sched = salary_schedule()
    etype = entity_type(bid)
    s_lo, s_hi, s_src = staff or STAFF_DEFAULTS[etype]
    g_lo, g_hi, g_src = avg_sg or AVG_STAFF_SG
    m_lo, m_hi, m_src = mooe or MOOE_SHARE
    head_sg = max([x["sg"] for x in b["facts"]["salary_grades"]] or [0])
    head = annual_cost_per_person(sched[head_sg]) if head_sg in sched else 0.0

    # Method A: bottom-up
    ps_lo = head + s_lo * annual_cost_per_person(sched[g_lo])
    ps_hi = head + s_hi * annual_cost_per_person(sched[g_hi])
    a_lo, a_hi = ps_lo * (1 + m_lo), ps_hi * (1 + m_hi)

    # Method B: comparators (all-in obligations per staff member)
    comps = []
    for c in comparators():
        names = comparator_names or COMPARATOR_DEFAULTS.get(etype, [])
        if names and c["agency"] not in names:
            continue
        # denominator: all personnel if reported, else AUTHORIZED positions (not filled ones, which
        # would load the whole agency's spending onto fewer people and inflate the per-staff cost)
        staff_n = float(c["personnel_total"] or c["plantilla_authorized"] or c["plantilla_filled"] or 0)
        oblig = c.get("obligations_operating") or c["obligations"]      # excludes large program funds where the report shows them
        if staff_n and oblig:
            comps.append({"agency": c["agency"], "year": c["year"], "per_staff": float(oblig) / staff_n,
                          "denominator": "personnel_total" if c["personnel_total"] else "plantilla_authorized" if c["plantilla_authorized"] else "plantilla_filled",
                          "note": "All-in: total agency obligations (including programs) per staff member; an upper-bound benchmark", "source": c["source"]})
    if comps:
        per = sorted(x["per_staff"] for x in comps)
        b_lo, b_hi = s_lo * per[0], s_hi * per[-1]
    else:
        b_lo = b_hi = None

    stated = [{"pesos": a["pesos"], "section": f"{bid}:s{a['section']}", "quote": a["quote"]} for a in b["facts"]["amounts"]]
    lo = min(x for x in (a_lo, b_lo) if x is not None)
    hi = max(x for x in (a_hi, b_hi) if x is not None)
    assumptions = [
        {"assumption": f"Entity type: {etype}", "source": f"{bid} title (classified by rule)", "to_verify": True},
        {"assumption": f"Headcount {s_lo:,}-{s_hi:,}", "source": s_src, "to_verify": True},
        {"assumption": f"Average staff salary grade SG-{g_lo} to SG-{g_hi}, Step 1", "source": g_src, "to_verify": True},
        {"assumption": f"MOOE {m_lo:.0%}-{m_hi:.0%} of personnel cost", "source": m_src, "to_verify": True},
        {"assumption": "Monthly salaries from the 2026 salary schedule (third tranche under EO 64 s. 2024)", "source": "DBM NBC No. 601, Annex A (data/benchmarks/salary_schedule_2026.csv)", "to_verify": False},
        {"assumption": "Method B uses total agency obligations per staff member, which include program funds: treat its top as an upper bound", "source": "data/benchmarks/coa_comparators.csv", "to_verify": True},
    ]
    if head_sg:
        assumptions.insert(1, {"assumption": f"Head of agency at SG-{head_sg}, Step 1: P{sched[head_sg]:,}/month", "source": f"{bid} (salary grade stated in the bill)", "to_verify": False})
    assumptions += [{"assumption": n, "source": s, "to_verify": True} for n, _, _, s in BENEFITS]
    return {
        "bill": bid, "entity_type": etype, "currency": "PHP", "period": "first full year",
        "method_a_bottom_up": {"low": round(a_lo), "high": round(a_hi), "personnel_low": round(ps_lo), "personnel_high": round(ps_hi)},
        "method_b_comparators": {"low": round(b_lo) if b_lo else None, "high": round(b_hi) if b_hi else None, "comparators": comps},
        "range": {"low": round(lo), "high": round(hi)},
        "stated_in_bill": stated,
        "assumptions": assumptions,
        "caveats": ["Order-of-magnitude range for a preliminary review, not a costing for budget purposes.",
                    "Excludes capital outlay, regional offices beyond the comparators' scale, and transfers of existing personnel and budgets from abolished offices (which reduce the net new cost).",
                    "Assumptions marked 'to verify' must be confirmed by the reviewer."],
    }


def peso(x):
    return f"P{x / 1e6:,.1f} million" if x < 1e9 else f"P{x / 1e9:,.2f} billion"


if __name__ == "__main__":
    import json
    import sys
    r = cost_range(sys.argv[1] if len(sys.argv) > 1 else "SB-20-1624")
    print(json.dumps({k: v for k, v in r.items() if k != "assumptions"}, indent=1)[:2500])
    print("Range:", peso(r["range"]["low"]), "to", peso(r["range"]["high"]))
