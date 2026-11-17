"""Rough budgetary requirements of a new entity or new positions: Personnel Services (PS), Maintenance and Other
Operating Expenses (MOOE) and Capital Outlay (CO), computed in the background (no AI).

Method, following the way DBM costs the creation of a new office (organization and staffing standards, then MOOE and
CO from existing rules and market prices):
  1. Structure: from a headcount, the number of bureaus, services or offices (about one per 16 positions), division
     chiefs (1.6 per office), key officials by entity type, and staff.
  2. PS: 2026 salary schedule (NBC No. 601) with mandatory benefits (agents/costing.py), by position level.
  3. MOOE: per-person, per-office and per-official rates (travel under EO No. 77, s. 2019; training under NBC No. 563;
     extraordinary and miscellaneous expenses under the General Provisions of the GAA; rent under DBM-DPWH Joint
     Circular No. 1; utilities, supplies, communication, janitorial and security services from agency benchmarks).
  4. CO (first year only): ICT equipment, printers, furniture and fixtures per person and per office; motor vehicles
     under DBM Budget Circular Nos. 2022-1 and 2022-1A.
Rates are 2023 price levels from DBM costing references; they give an order of magnitude, not a budget proposal.
"""
from agents.costing import annual_cost_per_person, salary_schedule

BASIS = "2023 price levels; DBM costing parameters for the creation of a new office"
# key officials and their salary grades, by entity type (head, deputies)
OFFICIALS = {
    "department": {"head": 31, "deputies": [(30, 4), (29, 4)]},
    "authority": {"head": 30, "deputies": [(29, 2)]},
    "commission": {"head": 30, "deputies": [(29, 2)]},
    "bureau": {"head": 28, "deputies": [(27, 1)]},
    "council": {"head": 29, "deputies": []},
    "office": {"head": 29, "deputies": [(28, 1)]},
}
SG_DIRECTOR, SG_CHIEF = 28, 24
VEHICLE = {31: 2_800_000, 30: 1_800_000, 29: 1_500_000, 28: 1_400_000}     # officials entitled to a vehicle (BC 2022-1)
SERVICE_VEHICLE = 2_650_000
MOBILE = {31: 60_000, 30: 42_000, 29: 30_000, 28: 21_600, 24: 9_600}      # annual mobile allowance by level
EME = {31: 264_000, 30: 108_000, 29: 60_000, 28: 45_600}                  # extraordinary expenses by level

RATES = [  # (MOOE item, per person, per office, per official/vehicle note) -- annual pesos
    ("Travelling expenses", "Officials travel monthly (P197,988 a year each); directors quarterly (P65,996); half of the staff travel "
     "quarterly for the mandate (P65,996); every employee attends one out-of-town seminar (P16,499). EO No. 77, s. 2019"),
    ("Training expenses", "P21,000 per employee a year (three trainings at P6,000 and one at P3,000) and P10,000 per office; NBC No. 563"),
    ("Supplies and materials", "Office supplies P20,000 per employee a year; fuel for vehicles (60 litres a week for officials' "
     "vehicles, 70 litres for service vehicles, at P85 a litre)"),
    ("Utilities", "Drinking water P960, utility water P6,704 and electricity P60,335 per employee a year (agency benchmarks)"),
    ("Communication", "Postage P1,676 per employee; landlines P156,000 per office; mobile allowance by rank (COA policy)"),
    ("Extraordinary and miscellaneous expenses", "By rank of official, plus P90,000 per office (General Provisions of the GAA)"),
    ("General services", "Janitors (one per office plus five) and security guards (one per 12 employees, at least three) "
     "at P12,540 a month each"),
    ("Rent", "12.8 sq. m. of office space per employee at P850 per sq. m. a month (DBM-DPWH Joint Circular No. 1); a photocopier "
     "per office at P10,000 a month"),
    ("Other MOOE", "Representation (P110,880 per office and P1,000 per employee), advertising, printing, subscriptions and vehicle "
     "registration, scaled to the size of the office"),
]
CO_NOTES = [
    ("ICT equipment", "A desktop computer per employee (P42,391); a laptop, projector and recorder per office (P66,308)"),
    ("Printers", "Two monochrome and one colour laser printer per office (P21,094)"),
    ("Furniture and fixtures", "Officials P56,700, division chiefs P24,698 and staff P15,550 each; common-area sofa and a "
     "conference set per office (P104,576)"),
    ("Motor vehicles", "For officials at Director level and above in departments, authorities and bureaus (DBM Budget Circular "
     "Nos. 2022-1 and 2022-1A), and one service vehicle per 36 employees"),
]


def structure(n, etype, head_sg=None):
    o = OFFICIALS.get(etype, OFFICIALS["office"])
    offices = max(2, round(n / 16))
    head = [(head_sg or o["head"], 1)]
    deputies = list(o["deputies"])
    directors = offices if etype in ("department", "authority", "bureau") else max(1, round(offices / 3))
    chiefs = round(offices * 1.6)
    n_off = 1 + sum(c for _, c in deputies) + directors + chiefs
    staff = max(1, n - n_off)
    return {"headcount": n_off + staff, "offices": offices, "head": head, "deputies": deputies, "directors": directors,
            "division_chiefs": chiefs, "staff": staff, "service_vehicles": max(1, round(n / 36)),
            "official_vehicles": etype in ("department", "authority", "bureau")}


def estimate(n, etype, head_sg=None, staff_sg=13):
    """PS, MOOE and CO (pesos) for a headcount n."""
    sched = salary_schedule()
    s = structure(n, etype, head_sg)
    people = s["head"] + s["deputies"] + [(SG_DIRECTOR, s["directors"]), (SG_CHIEF, s["division_chiefs"]), (staff_sg, s["staff"])]
    ps = sum(annual_cost_per_person(sched[g]) * c for g, c in people if g in sched)
    officials = s["head"] + s["deputies"]
    n_off = sum(c for _, c in officials)
    N, O = s["headcount"], s["offices"]
    veh_off = (n_off + s["directors"]) if s["official_vehicles"] else 0
    veh = veh_off + s["service_vehicles"]
    scale = max(0.2, N / 358)
    mooe = {
        "Travelling expenses": 197_988 * n_off + 65_996 * s["directors"] + 65_996 * round(s["staff"] / 2) + 16_499 * N,
        "Training expenses": 21_000 * N + 10_000 * O,
        "Supplies and materials": 20_000 * N + 2_880 * 85 * veh_off + 3_360 * 85 * s["service_vehicles"],
        "Utilities": (960 + 6_704 + 60_335) * N,
        "Communication": 1_676 * N + 156_000 * O + sum(MOBILE.get(g, 21_600) * c for g, c in officials)
                         + MOBILE[28] * s["directors"] + MOBILE[24] * s["division_chiefs"],
        "Extraordinary and miscellaneous expenses": sum(EME.get(g, 45_600) * c for g, c in officials) + EME[28] * s["directors"] + 90_000 * O,
        "General services": 12_540 * 12 * ((O + 5) + max(3, round(N / 12))),
        "Rent": round(12.8 * N) * 850 * 12 + 120_000 * O,
        "Other MOOE": 110_880 * O + 1_000 * N + round((726_996 + 1_074_996 + 3_180_000) * scale) + 2_400 * veh,
    }
    co = {
        "ICT equipment": 42_391 * N + 66_308 * O + 8_000 * max(1, round(O / 6)),
        "Printers": 21_094 * O,
        "Furniture and fixtures": 56_700 * (n_off + s["directors"]) + 24_698 * s["division_chiefs"] + 15_550 * s["staff"] + 104_576 * O,
        "Motor vehicles": (sum(VEHICLE.get(g, 1_400_000) * c for g, c in officials) + VEHICLE[28] * s["directors"]
                           if s["official_vehicles"] else 0) + SERVICE_VEHICLE * s["service_vehicles"],
    }
    total_mooe, total_co = sum(mooe.values()), sum(co.values())
    return {"structure": s, "ps": round(ps), "mooe": round(total_mooe), "co": round(total_co),
            "total": round(ps + total_mooe + total_co), "recurring": round(ps + total_mooe),
            "mooe_items": {k: round(v) for k, v in mooe.items()}, "co_items": {k: round(v) for k, v in co.items()}}


def requirements(cost):
    """Low and high estimates for the headcount range the costing engine set for the bill."""
    import re
    m = re.search(r"Headcount ([\d,]+)-([\d,]+)", " ".join(a["assumption"] for a in cost["assumptions"]))
    lo, hi = (int(m.group(1).replace(",", "")), int(m.group(2).replace(",", ""))) if m else (50, 150)
    head = re.search(r"SG-(\d+), Step 1", " ".join(a["assumption"] for a in cost["assumptions"] if a["assumption"].startswith("Head")))
    hsg = int(head.group(1)) if head else None
    return {"low": estimate(lo, cost["entity_type"], hsg, 13), "high": estimate(hi, cost["entity_type"], hsg, 18),
            "basis": BASIS, "mooe_notes": RATES, "co_notes": CO_NOTES}
