"""Deterministic first-year cost range for a bill that creates a government entity.

The AI never does arithmetic. Agent 3 narrates the numbers produced here, and the
verifier rejects any peso figure in its draft that this engine (or the bill) did not produce.

Two methods, reported side by side:
  A. Bottom-up personnel cost: head of agency at the salary grade the bill sets (if any)
     + staff (low/high headcount) at an assumed average salary grade, loaded with
     mandatory benefits; plus maintenance and other operating expenses (MOOE) as a
     share of personnel cost.
  B. Top-down comparator: operating cost per authorized position of comparable agencies
     in the FY 2026 GAA (Personnel Services plus the MOOE of General Administration and Support
     and Support to Operations, divided by the authorized positions in the DBM Staffing Summary
     FY 2026) x the same headcount range. Program spending (Operations) and capital outlay are left out.
     COA audit figures (all-in obligations per staff member) are kept as a cross-check.
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
    "department": (552, 1896, "DHSUD had 552 personnel in its first full year (COA 2020); DMW's Office of the Secretary has 1,896 authorized positions in FY 2026 (DBM Staffing Summary FY 2026) (to verify)"),
    "authority": (100, 400, "NWRB has 124 authorized positions (DBM Staffing Summary FY 2026; COA 2025); reviewer to adjust for mandate"),
    "commission": (76, 124, "Authorized positions of comparators: Climate Change Commission 76, NWRB 124 (DBM Staffing Summary FY 2025-2026); the bill itself sets no staffing (to verify)"),
    "bureau": (100, 300, "Reviewer to set; Cooperative Development Authority (879) and BFAR (2,126) are much larger (DBM Staffing Summary FY 2026)"),
    "council": (15, 60, "Reviewer to set; small secretariat assumed"),
    "office": (30, 150, "Reviewer to set"),
}
# Comparators matched to entity type (program-heavy agencies like BFAR or OCD are excluded
# from per-staff benchmarks because their obligations include large program funds).
COMPARATOR_DEFAULTS = {
    "department": ["Department of Human Settlements and Urban Development", "Department of Migrant Workers"],
    "authority": ["National Water Resources Board", "Cooperative Development Authority"],
    "commission": ["Climate Change Commission", "National Water Resources Board"],
    "bureau": ["Bureau of Fisheries and Aquatic Resources", "Cooperative Development Authority"],
    "council": ["Climate Change Commission"],
    "office": ["Climate Change Commission", "National Water Resources Board"],
}
MOOE_SHARE = (0.31, 0.64, "Overhead MOOE (General Administration and Support plus Support to Operations) as a share of "
              "Personnel Services: middle half of 9 comparator agencies in the FY 2026 GAA, median 36% (data/benchmarks/gaa_2026_by_agency.csv)")
AVG_STAFF_SG = (13, 18, "Average staff salary grade (Step 1). Consistent with the FY 2026 GAA: Personnel Services per authorized position "
                "of 8 comparators is P0.56M-P0.86M, close to the engine's loaded cost of P0.62M at SG-13 and P0.90M at SG-18 (DMW, with overseas posts, P1.35M); "
                "reviewer to confirm against a draft staffing pattern")
# Prices: the 2026 salary schedule is the last tranche under EO 64 s. 2024, so personnel cost is not inflated. MOOE in
# 2027 prices would be higher by the 2027 inflation assumption.
PRICE_2027 = (0.04, 0.05, "DBM 2027 Budget Priorities Framework: inflation assumption 4.0-5.0% for 2027 (2026: 6.0-7.0%); "
              "PSA: headline inflation 7.8% in October 2026, 5.6% January-October")


def salary_schedule():
    out = {}
    with open(BENCH / "salary_schedule_2026.csv") as f:
        for r in csv.DictReader(f):
            out[int(r["salary_grade"])] = int(r["step_1"])
    return out


def comparators():
    """COA audit figures (cross-check)."""
    with open(BENCH / "coa_comparators.csv") as f:
        return list(csv.DictReader(f))


def gaa_comparators():
    """FY 2026 GAA operating cost per authorized position (Method B)."""
    with open(BENCH / "gaa_2026_by_agency.csv") as f:
        gaa = {(r["department"], r["agency"]): r for r in csv.DictReader(f)}
    out = []
    with open(BENCH / "staffing_summary_2026.csv") as f:
        for s in csv.DictReader(f):
            g = gaa.get((s["gaa_department"], s["gaa_agency"]))
            if not g:
                continue
            tot = lambda pre: sum(float(v) for k, v in g.items() if k.startswith(pre)) * 1000
            ps, mooe = tot("ps_"), tot("mooe_")
            ovh = (float(g["mooe_gas"]) + float(g["mooe_sto"])) * 1000
            n = int(s["permanent_positions_2026"])
            out.append({"agency": s["agency"], "positions": n, "personnel_services": round(ps), "mooe_overhead": round(ovh),
                        "mooe_total": round(mooe), "overhead_mooe_share": round(ovh / ps, 2) if ps else None,
                        "per_position": (ps + ovh) / n if n else None, "year": "2026",
                        "source": f"GAA FY 2026 by object (DBM); {s['source']}" + (f" ({s['note']})" if s.get("note") else "")})
    return out


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

    names = comparator_names or COMPARATOR_DEFAULTS.get(etype, [])
    # Method B: FY 2026 GAA operating cost (PS + overhead MOOE) per authorized position
    comps = [dict(c, note="Personnel Services plus overhead MOOE per authorized position, FY 2026 (programs and capital outlay excluded)")
             for c in gaa_comparators() if not names or c["agency"] in names]
    if comps:
        per = sorted(x["per_position"] for x in comps)
        b_lo, b_hi = s_lo * per[0], s_hi * per[-1]
    else:
        b_lo = b_hi = None
    # Cross-check: COA all-in obligations per staff member (includes program funds)
    coa = []
    for c in comparators():
        if names and c["agency"] not in names:
            continue
        # denominator: all personnel if reported, else AUTHORIZED positions (not filled ones, which
        # would load the whole agency's spending onto fewer people and inflate the per-staff cost)
        staff_n = float(c["personnel_total"] or c["plantilla_authorized"] or c["plantilla_filled"] or 0)
        oblig = c.get("obligations_operating") or c["obligations"]      # excludes large program funds where the report shows them
        if staff_n and oblig:
            coa.append({"agency": c["agency"], "year": c["year"], "per_staff": float(oblig) / staff_n,
                        "denominator": "personnel_total" if c["personnel_total"] else "plantilla_authorized" if c["plantilla_authorized"] else "plantilla_filled",
                        "note": "All-in: total agency obligations (including programs) per staff member; cross-check only", "source": c["source"]})
    p_lo, p_hi, p_src = PRICE_2027
    mooe_2027 = {"low": round((a_lo - ps_lo) * p_lo), "high": round((a_hi - ps_hi) * p_hi)}

    stated = [{"pesos": a["pesos"], "section": f"{bid}:s{a['section']}", "quote": a["quote"]} for a in b["facts"]["amounts"]]
    lo = min(x for x in (a_lo, b_lo) if x is not None)
    hi = max(x for x in (a_hi, b_hi) if x is not None)
    assumptions = [
        {"assumption": f"Entity type: {etype}", "source": f"{bid} title (classified by rule)", "to_verify": True},
        {"assumption": f"Headcount {s_lo:,}-{s_hi:,}", "source": s_src, "to_verify": True},
        {"assumption": f"Average staff salary grade SG-{g_lo} to SG-{g_hi}, Step 1", "source": g_src, "to_verify": True},
        {"assumption": f"MOOE {m_lo:.0%}-{m_hi:.0%} of personnel cost", "source": m_src, "to_verify": True},
        {"assumption": "Monthly salaries from the 2026 salary schedule (third tranche under EO 64 s. 2024)", "source": "DBM NBC No. 601, Annex A (data/benchmarks/salary_schedule_2026.csv)", "to_verify": False},
        {"assumption": "Method B: Personnel Services plus overhead MOOE per authorized position of comparable agencies (FY 2026); program spending and capital outlay excluded", "source": "GAA FY 2026 by object (DBM) and DBM Staffing Summary FY 2026 (data/benchmarks/gaa_2026_by_agency.csv, staffing_summary_2026.csv)", "to_verify": True},
        {"assumption": f"Figures are in 2026 prices. If the entity starts in 2027, MOOE would be about {p_lo:.0%}-{p_hi:.0%} higher (P{mooe_2027['low'] / 1e6:,.1f}M-P{mooe_2027['high'] / 1e6:,.1f}M); salaries stay at the 2026 schedule unless a new salary law is passed", "source": p_src, "to_verify": True},
        {"assumption": "COA audit figures (all-in obligations per staff member, including programs) are shown as a cross-check, not used in the range", "source": "data/benchmarks/coa_comparators.csv", "to_verify": False},
    ]
    if head_sg:
        assumptions.insert(1, {"assumption": f"Head of agency at SG-{head_sg}, Step 1: P{sched[head_sg]:,}/month", "source": f"{bid} (salary grade stated in the bill)", "to_verify": False})
    assumptions += [{"assumption": n, "source": s, "to_verify": True} for n, _, _, s in BENEFITS]
    return {
        "bill": bid, "entity_type": etype, "currency": "PHP", "period": "first full year",
        "method_a_bottom_up": {"low": round(a_lo), "high": round(a_hi), "personnel_low": round(ps_lo), "personnel_high": round(ps_hi)},
        "method_b_comparators": {"low": round(b_lo) if b_lo else None, "high": round(b_hi) if b_hi else None,
                                 "comparators": [dict(c, per_position=round(c["per_position"])) for c in comps]},
        "coa_crosscheck": [dict(c, per_staff=round(c["per_staff"])) for c in coa],
        "mooe_2027_price_effect": mooe_2027,
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
