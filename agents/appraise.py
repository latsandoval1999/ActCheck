"""ApprAIsal (Agent 3), version 3: fiscal and budgetary requirements, possible duplication, overall recommendation.

Building on TrAIce (fiscal requirements, related laws) and CompAIre (decision points, duplications, cost effects):
  Part V   Fiscal and Budgetary Requirements: per item, the provision, what the bill provides, the recommended budgetary
           consideration (from the PS, MOOE and CO estimate in agents/budget.py and the costing engine), the recommendation
           on budgetary capacity and the GAA, and the risks.
  Part VI  Possible Duplication with Existing Agencies (only when detected): whether the bill intends to change or
           abolish the existing body; if not, an assessment under the Government Optimization Act (RA No. 12231).
  Part VII Recommendation, one of three options (worded as in DBM memoranda), with the points to address.
It also lists the DBM bureaus and offices to consult (functional statements in the DBM Charter, CY 2026) and compiles
memo Parts I to VII without repeating statements. The reviewer confirms the recommendation; the agent proposes it.
"""
import json
import re
from pathlib import Path

from pipeline.compare import load
from agents import traice, budget
from agents.costing import peso, salary_schedule, annual_cost_per_person

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "data" / "agent_runs"
PROMPT_VERSION = "v3"
OPTIONS = {
    "a": ("Interpose no objection", "This Department interposes no objection to the proposed measure as filed."),
    "b": ("Interpose no objection, subject to amendments",
          "This Department interposes no objection to the proposed measure, subject to the incorporation of the recommendations."),
    "c": ("Constrained from supporting the proposed measure",
          "This Department recommends that further consideration of the proposed measure be deferred until the issues identified "
          "in this review have been adequately addressed."),
}
GOA = ("the Government Optimization Act (RA No. 12231), signed on August 4, 2025, which seeks to promote effectiveness, "
       "efficiency and economy in government and authorizes the merger or consolidation of agencies whose functions are "
       "unnecessarily overlapping or duplicating (Section 6)")
GOA_OTHER = ("Section 21 of the same Act requires the other branches of government to observe its principles in optimizing "
             "their own offices")
# Who to consult, from the functional statements in the DBM Charter (CY 2026)
BUREAUS = {
    "OPCCB": ("Organization, Position Classification and Compensation Bureau",
              "Evaluates organization and staffing proposals and administers the compensation and position classification system"),
    "BTB": ("Budget Technical Bureau", "Sets budget standards, prepares the President's Budget and administers special funds"),
    "BMB": ("Budget and Management Bureau with coverage of the agency or sector concerned",
            "Reviews the agencies' medium-term expenditures and budget allocations"),
    "SPIB": ("Systems and Productivity Improvement Bureau", "Sets policies and standards for systems improvement, productivity and bureaucratic reform"),
    "LS": ("Legal Service", "Provides legal guidance and reviews legislative measures and issuances"),
    "LGRCB": ("Local Government and Regional Coordination Bureau", "Administers LGU allocations and local budget policies"),
    "FPRB": ("Fiscal Planning and Reforms Bureau", "Conducts fiscal policy research and budget frameworks"),
}
SOURCE_BUREAUS = "DBM Charter, CY 2026 (functional statements); DBM Central Office Directory (coverage agencies)"
COVERAGE = json.loads((Path(__file__).resolve().parents[1] / "data" / "reference" / "dbm_bureau_coverage.json").read_text())
for _code, _b in COVERAGE["bureaus"].items():
    if _code.startswith("BMB-"):
        BUREAUS[_code] = (f"Budget and Management Bureau-{_code[-1]}",
                          "Reviews the medium-term expenditures and budget allocations of its coverage agencies ("
                          + ", ".join(a[1] or a[0].replace(" of the Philippines", "") for a in _b["agencies"][:6]) + (", and others)" if len(_b["agencies"]) > 6 else ")"))
BUREAUS["LGRCB"] = (BUREAUS["LGRCB"][0], BUREAUS["LGRCB"][1] + " (coverage: National Tax Allotment and allocations to LGUs)")
EMAIL = {c: b["email"] for c, b in COVERAGE["bureaus"].items()}


def _agency_patterns():
    out = []
    for code, b in COVERAGE["bureaus"].items():
        for name, acr in b["agencies"]:
            names = [name] + COVERAGE["aliases"].get(name, [])
            out.append((code, name, acr, re.compile(r"\b(" + "|".join(re.escape(n) for n in names if n) + r")\b", re.I)))
    return out


AGENCY_PATTERNS = _agency_patterns()


def _and(xs):
    xs = list(xs)[:4]
    return xs[0] if len(xs) == 1 else ", ".join(xs[:-1]) + " and " + xs[-1]


def coverage(bid, t_out=None):
    """The Budget and Management Bureaus concerned, from the coverage agencies named in the bill.
    funding: the agency whose budget the bill charges; attached: the agency the new office is attached to;
    sector: other agencies the bill names at least twice (members, implementers). The enacting clause is ignored."""
    secs = load()[1].get(bid, [])
    def body(s):
        return re.sub(r"(Be it enacted|in Congress assembled)[^.:]*[.:]", " ", s["heading"] + ". " + s["text"], flags=re.I)
    allt = " ".join(body(s) for s in secs)
    fund = " ".join(body(s) for s in secs if re.search(r"appropriat|funding|budget", s["heading"], re.I))
    attach = " ".join(m.group(1) for m in re.finditer(r"attached to the ([A-Z][^.;,]{5,90})", allt))
    moved = " ".join(body(s) for s in secs if re.search(r"transfer of (functions|powers|resources|personnel|assets)|abolition|absorption|"
                                                         r"\babolish|\babsorb", s["heading"], re.I))
    found = {}
    for code, name, acr, pat in AGENCY_PATTERNS:
        n_all, n_fund, n_att = len(pat.findall(allt)), len(pat.findall(fund)), len(pat.findall(attach))
        n_mov = len(pat.findall(moved))
        if not (n_all or n_fund):
            continue
        if acr and len(acr) >= 3 and acr.isupper() and re.search(re.escape(name) + r"\s*\(" + re.escape(acr) + r"\)", allt, re.I):
            # the bill names the agency in full with its acronym once, then uses the acronym
            ap = re.compile(r"\b" + re.escape(acr) + r"\b")
            n_all, n_fund, n_att = n_all + len(ap.findall(allt)) - 1, n_fund + len(ap.findall(fund)), n_att + len(ap.findall(attach))
            n_mov += len(ap.findall(moved))
        role = ("funding" if n_fund else "transfer" if n_mov else "attached" if n_att else
                "sector" if n_all >= 2 and code != "LGRCB" else "")
        if code == "BMB-C" and name.startswith("Congress") and role == "sector":
            role = ""    # "Congress", "Senate" and "House" appear in most bills; count them only when they fund the measure
        if role:
            g = found.setdefault(code, {"bureau": code, "by_role": {}, "mentions": 0})
            g["mentions"] += n_all
            label = f"{name} ({acr})" if acr and re.search(r"\b" + re.escape(acr) + r"\b", allt) else name
            if all(label not in v for v in g["by_role"].values()):
                g["by_role"].setdefault(role, []).append(label)
    order = {"funding": 0, "transfer": 1, "attached": 1, "sector": 2}
    out = sorted(found.values(), key=lambda g: (min(order[r] for r in g["by_role"]), -g["mentions"]))
    # bureaus concerned only because the bill gives their agencies a role: the two most involved
    out = [g for g in out if set(g["by_role"]) != {"sector"}] + [g for g in out if set(g["by_role"]) == {"sector"}][:2]
    for g in out:
        g["role"] = min(g["by_role"], key=order.get)
        g["agencies"] = [a for r in sorted(g["by_role"], key=order.get) for a in g["by_role"][r]]
    return out


def _doc(bid):
    return traice._doc(bid)


def _abolishes(bid):
    """Does the bill provide for abolishing, merging or transferring an existing office or its functions?"""
    bills, secs = load()
    f = (bills.get(bid) or {}).get("facts") or {}
    if f.get("abolishes_or_transfers"):
        return True
    return any(re.search(r"abolish|transfer|merg|absorb|consolidat", s["heading"], re.I) for s in secs.get(bid, []))


OFFICE_RX = (r"\b(DEPARTMENT|AUTHORITY|COMMISSION|OFFICE|BUREAU|COUNCIL|BOARD|AGENCY|INSTITUTE|CENTER|CENTRE|CORPORATION|"
             r"SECRETARIAT|COMMITTEE|ADMINISTRATION|UNIVERSITY|COLLEGE|SERVICE|DIVISION|UNIT)\b")


def _creates(bid, t_out=None):
    """Does the bill create a new office or body (not only a program, fund or framework)?"""
    name = (t_out or {}).get("entity_proposed") or ""
    if not name:
        m = re.search(r"\b(?:CREATING|ESTABLISHING)\s+(?:THE\s+|A\s+|AN\s+)?([^,]{5,120})", (load()[0].get(bid) or {}).get("title", "").upper())
        name = m.group(1) if m else ""
    return bool(re.search(OFFICE_RX, name.upper()))


def _branch(entity):
    return "legislative" if re.search(r"congressional|congress", entity or "", re.I) else "executive"


def fiscal_rows(bid, t_out, c_out, cost, req):
    """Part V table: item, provision, existing requirement, recommended consideration, recommendation, risks."""
    lo, hi = req["low"], req["high"]
    est = (f"about {peso(lo['total'])} to {peso(hi['total'])} in the first year for {lo['structure']['headcount']:,} to "
           f"{hi['structure']['headcount']:,} positions (PS {peso(lo['ps'])} to {peso(hi['ps'])}; MOOE {peso(lo['mooe'])} to "
           f"{peso(hi['mooe'])}; CO {peso(lo['co'])} to {peso(hi['co'])}, one-time)")
    rec_years = f"{peso(lo['recurring'])} to {peso(hi['recurring'])} a year thereafter (PS and MOOE)"
    sched = salary_schedule()
    office = _creates(bid, t_out)
    if not office:                     # a program or a measure without a new office: the new-office estimate does not apply
        est = "the program's benefits and implementation costs, which depend on its coverage (to be costed with the implementing agency)"
        rec_years = "the program's benefits and implementation costs every year, which depend on its coverage"
    rows, secretariat_seen = [], False
    for f in t_out.get("fiscal_requirements") or []:
        item, detail, sec = f.get("item", ""), f.get("detail", ""), f.get("section", "")
        low = item.lower()
        if low.startswith("comparator"):
            continue
        if "initial" in low:
            src_cong = bool(re.search(r"Senate|House", detail))
            rows.append({"item": "Initial funding", "provision": sec, "existing": detail,
                         "consideration": f"Estimated requirement of {est}." if office else f"Requirement covers {est}.",
                         "recommendation": ("The initial requirement may be charged to the available appropriations of the Senate and the House, as "
                                            "provided, but the amount should be stated so that it can be programmed." if src_cong else
                                            "The initial requirement may be sourced from available appropriations in the year of effectivity; "
                                            "otherwise it should be included in the succeeding GAA, subject to fiscal space."),
                         "risks": "An unstated amount may delay operations or crowd out the existing budgets it is charged to."})
        elif "continuing" in low:
            rows.append({"item": "Continuing funding", "provision": sec, "existing": detail,
                         "consideration": f"Recurring requirement of {rec_years}." if office else f"Recurring requirement covers {rec_years}.",
                         "recommendation": "The requirements may be included in the annual budget proposal under the budget call for the succeeding "
                                           "GAA (FY 2028 at the earliest), subject to fiscal space and the DBM's evaluation.",
                         "risks": "Competes with other priorities within the expenditure ceilings of the Budget Priorities Framework."})
        elif "position" in low:
            sg = re.search(r"Salary Grade (\d+)|SG[- ]?(\d+)", detail)
            g = int(next(x for x in sg.groups() if x)) if sg else None
            cost1 = f"{peso(annual_cost_per_person(sched[g]))} a year with mandatory benefits (SG {g}, Step 1, 2026 salary schedule)" if g in sched else "to be computed"
            rows.append({"item": "Position", "provision": sec, "existing": detail,
                         "consideration": f"About {cost1}." if g in sched else "No salary grade stated; to be set in the staffing pattern.",
                         "recommendation": "The position title and salary grade are subject to evaluation under the Compensation and Position "
                                           "Classification System and the organization and staffing standards.",
                         "risks": "A grade above comparable positions may create pay distortions across similar offices."})
        elif ("support" in low or "secretariat" in detail.lower()) and secretariat_seen and "existing agency" not in detail.lower():
            rows.append({"item": "Support body", "provision": sec, "existing": detail,
                         "consideration": "Meeting and honoraria expenses form part of MOOE in the estimate.",
                         "recommendation": "Members of advisory bodies to serve without additional positions; honoraria, if any, subject to existing rules.",
                         "risks": "Additional bodies add coordination and meeting costs."})
        elif "support" in low or "secretariat" in detail.lower():
            existing_agency = "existing agency" in detail.lower()
            secretariat_seen = secretariat_seen or not existing_agency
            rows.append({"item": "Support body", "provision": sec, "existing": detail,
                         "consideration": ("Requirements to be charged to the existing agency's budget." if existing_agency else
                                           f"Staffing of {lo['structure']['headcount']:,} to {hi['structure']['headcount']:,} positions assumed in the estimate."
                                           if office else "No new positions assumed; support to be provided by the agencies concerned."),
                         "recommendation": ("Any added requirement of the existing agency should be included in its own budget proposal." if existing_agency else
                                            "The organizational structure and staffing pattern should be submitted to the DBM for review before positions are filled."),
                         "risks": ("Competes with the agency's other work." if existing_agency else
                                   "Staffing may grow beyond the body's term or mandate if not time-bound.")})
        elif "member" in low:
            rows.append({"item": "Members", "provision": sec, "existing": detail,
                         "consideration": "Travel and meeting expenses form part of MOOE in the estimate.",
                         "recommendation": "Allowable expenses should be limited to actual travel and meetings, consistent with existing rules on travel "
                                           "(EO No. 77, s. 2019) and honoraria.",
                         "risks": "Open-ended allowances may increase MOOE."})
    if not rows:
        rows.append({"item": "Funding source", "provision": "None identified", "existing": "The bill has no appropriations clause.",
                     "consideration": f"Estimated requirement of {est}." if _creates(bid, t_out) else "Cost depends on implementation.",
                     "recommendation": "An appropriations clause identifying the source of funds and providing for inclusion in the GAA should be added.",
                     "risks": "An unfunded mandate may not be implemented."})
    return rows


def duplications(bid, t_out, c_out):
    entity = t_out.get("entity_proposed") or "the proposed body"
    intent = _abolishes(bid)
    out = []
    for d in (c_out or {}).get("duplications") or []:
        out.append(dict(d, intent_to_abolish=intent,
                        assessment=("The bill provides for the transfer or abolition of offices; its transition should follow RA No. 12231 "
                                    "(detailed structure and staffing to the DBM, benefits of affected personnel)." if intent else
                                    "The bill adds a body without changing or abolishing the existing one: a duplication to assess under RA No. 12231.")))
    return out, entity, intent


def recommend(bid, c_out, dups, intent, req, rows):
    issues = []
    for m in (c_out or {}).get("memo_part") or []:
        h = re.sub(r"^On (the )?", "", m.get("heading", "")).strip()
        issues.append(h[:1].upper() + h[1:])
    if any("amount should be stated" in r["recommendation"] for r in rows):
        issues.append("Amount of the initial funding")
    if dups and not intent:
        issues.append("Possible duplication with existing bodies, to be resolved in line with RA No. 12231")
    issues = list(dict.fromkeys(i for i in issues if i))
    big = req["low"]["total"] > 1e9
    if dups and not intent and big:
        key = "c"
    elif issues:
        key = "b"
    else:
        key = "a"
    return key, issues


def referrals(bid, t_out, c_out, dups, rows):
    bills, secs = load()
    text = " ".join(s["heading"] + " " + s["text"][:400] for s in secs.get(bid, [])).lower()
    out = []
    def add(code, why, parts):
        out.append({"bureau": code, "name": BUREAUS[code][0], "function": BUREAUS[code][1], "why": why, "parts": parts,
                    "email": EMAIL.get(code, "")})
    if any(r["item"] == "Position" for r in rows) or _creates(bid, t_out):
        add("OPCCB", "New positions, salary grades, organizational structure and staffing pattern", "Part V (Position; Support body)")
    if any(r["item"] in ("Initial funding", "Continuing funding", "Funding source") for r in rows):
        add("BTB", "Appropriations language and inclusion in the General Appropriations Act", "Part V (Initial and continuing funding)")
    groups = coverage(bid, t_out)
    for g in groups:
        if g["bureau"] == "LGRCB":
            continue
        br = g["by_role"]
        parts_ = []
        if br.get("funding"):
            parts_.append("the bill charges its requirements to the budget of the " + _and(br["funding"]))
        if br.get("transfer"):
            parts_.append("the bill's provisions on the transfer of functions, funds and positions concern the " + _and(br["transfer"]))
        if br.get("attached"):
            parts_.append("the new office is attached to the " + _and(br["attached"]))
        if br.get("sector"):
            parts_.append("the bill assigns a role to the " + _and(br["sector"]))
        why = "; ".join(parts_)
        why = why[:1].upper() + why[1:]
        add(g["bureau"], why, "Part V" if g["role"] != "sector" else "Parts IV and V")
    if not [g for g in groups if g["bureau"].startswith("BMB-")] and any(r["item"] in ("Initial funding", "Continuing funding", "Funding source") for r in rows):
        add("BMB", "Budgetary requirements of the agency or sector concerned (no coverage agency named in the bill; confirm the bureau)", "Part V")
    if dups:
        add("SPIB", "Possible duplication and rationalization of functions under RA No. 12231", "Part VI")
    if any(x.get("label") == traice.LAW_LABELS[0] for x in t_out.get("existing_law_overlaps", [])) or re.search(r"penalt|imprisonment|fine of", text):
        add("LS", "The bill amends existing laws or provides penalties", "Parts IV and VI")
    if re.search(r"local government units?.{0,80}(share|fund|allocation|appropriat)", text) or any(g["bureau"] == "LGRCB" for g in groups):
        add("LGRCB", "The bill affects LGU allocations or local budgets", "Part V")
    if req_big(rows):
        add("FPRB", "Large fiscal impact relative to the medium-term fiscal program", "Part V")
    return out


def req_big(rows):
    return False


def _numbered(n, items):
    return [f"{n}.{i} {t}" for i, t in enumerate(items, 1)]


def rule_draft(bid, t_out, c_out, cost):
    req = budget.requirements(cost)
    rows = fiscal_rows(bid, t_out, c_out, cost, req)
    dups, entity, intent = duplications(bid, t_out, c_out)
    key, issues = recommend(bid, c_out, dups, intent, req, rows)
    refs = referrals(bid, t_out, c_out, dups, rows)
    doc = _doc(bid)
    lo, hi = req["low"], req["high"]
    # Part V
    p5 = [f"Based on the organization and staffing standards and existing rules on maintenance and capital outlays, the creation of "
          f"{'the ' if not entity.lower().startswith('the ') else ''}{entity} would require about {peso(lo['total'])} to {peso(hi['total'])} in its first year, consisting of Personnel Services "
          f"of {peso(lo['ps'])} to {peso(hi['ps'])}, Maintenance and Other Operating Expenses of {peso(lo['mooe'])} to {peso(hi['mooe'])}, "
          f"and Capital Outlay of {peso(lo['co'])} to {peso(hi['co'])} (one-time), for {lo['structure']['headcount']:,} to "
          f"{hi['structure']['headcount']:,} positions. Thereafter, about {peso(lo['recurring'])} to {peso(hi['recurring'])} would be "
          "needed every year." if _creates(bid, t_out) else
          "The bill does not create a new office; its budgetary requirements depend on implementation by the agencies concerned."]
    for r in rows:
        if r["item"] in ("Initial funding", "Continuing funding", "Position", "Funding source"):
            where = f" under {r['provision']} of {doc}" if r["provision"] and r["provision"] != "None identified" else f" in {doc}"
            p5.append(f"As regards the {r['item'].lower()}{where}, {r['recommendation'][:1].lower() + r['recommendation'][1:]}")
    # Part VI
    p6 = []
    for d in dups:
        ex = re.sub(r"^the\s+", "", d.get("existing", "an existing body"), flags=re.I)
        base = (f"{d.get('function', 'The bill')} of {doc} appears to overlap with the {ex}. "
                f"{d.get('note', '').rstrip('.')}.")
        if not d["intent_to_abolish"]:
            base += (f" The bill does not provide for the abolition, merger or transfer of the existing body or its functions. In view of {GOA}, "
                     "the bill may be revisited to delineate the functions of the two bodies, or to assign the function to the existing body.")
            if _branch(entity) == "legislative":
                base += f" As the proposed body is under the Legislative branch, {GOA_OTHER}."
        else:
            base += " The bill provides for the transfer or abolition of the existing office, which is consistent with the objectives of RA No. 12231."
        p6.append(base)
    # Part VII
    p7 = [OPTIONS[key][1]]
    lst = "; ".join(f"({chr(97 + i)}) {x[:1].lower() + x[1:]}" for i, x in enumerate(issues))
    if key == "b" and issues:
        p7.append(f"In particular, the following should be addressed: {lst}.")
    if key == "c":
        p7.append(f"The issues and risks to be addressed are: {lst}.")
    checks = ["Confirm the headcount and staffing assumptions against a draft organizational structure and staffing pattern.",
              "Confirm the Budget and Management Bureaus to consult (matched from the agencies named in the bill and the DBM directory's coverage lists)."]
    if dups:
        checks.append("Confirm whether the existing body named in Part VI is still constituted and active.")
    if not _creates(bid, t_out):
        checks[0] = "Confirm the program's coverage (number of beneficiaries) and unit costs with the implementing agency, to cost the measure."
    return {"target": bid, "source": "rules", "estimate": {"low": _slim(lo), "high": _slim(hi), "basis": req["basis"],
                                                         "applies": _creates(bid, t_out)},
            "fiscal_rows": rows, "duplications": dups, "intent_to_abolish": intent,
            "recommendation": {"option": key, "label": OPTIONS[key][0], "issues": issues},
            "referrals": refs, "memo": {"V": _numbered(5, p5), "VI": _numbered(6, p6), "VII": _numbered(7, p7)},
            "reviewer_checks": checks}


def _slim(e):
    return {k: e[k] for k in ("ps", "mooe", "co", "total", "recurring")} | {"headcount": e["structure"]["headcount"]}


def memo_text(out):
    m = out.get("memo") or {}
    parts = []
    for k, title in (("V", "V. Fiscal and Budgetary Requirements"), ("VI", "VI. Possible Duplication with Existing Agencies"), ("VII", "VII. Recommendation")):
        if m.get(k):
            parts.append(title + "\n" + "\n".join(m[k]))
    return "\n\n".join(parts)


def harmonize(*texts):
    """Compile memo parts in order and drop sentences already stated in an earlier part."""
    seen, out = set(), []
    for t in texts:
        keep = []
        for line in str(t or "").split("\n"):
            sents = re.split(r"(?<=[.;])\s+", line)
            num = re.match(r"^(\d+\.\d+)\s+", line)
            new = []
            for s_ in sents:
                key = re.sub(r"\W+", " ", re.sub(r"^\d+(\.\d+)?\s+", "", s_).lower()).strip()
                if len(key) > 60 and key in seen:
                    continue
                seen.add(key)
                new.append(s_)
            if new and num and not new[0].startswith(num.group(1)):
                new[0] = num.group(1) + " " + new[0]
            if new:
                keep.append(" ".join(new))
        out.append("\n".join(keep))
    return out


def saved_ai(bid):
    p = RUNS / bid / "apprAIsal.json"
    try:
        return json.loads(p.read_text()) if p.exists() else None
    except Exception:
        return None


def normalize(out, bid, draft):
    if not out:
        return draft
    o = dict(draft)
    o.update({k: v for k, v in out.items() if v not in (None, [], {})})
    o["source"] = out.get("source", "ai")
    o["estimate"] = draft["estimate"]            # figures always come from the engine, never from the agent
    o["referrals"] = [dict(r, name=r.get("name") or BUREAUS.get(r.get("bureau"), ("", ""))[0],
                           function=r.get("function") or BUREAUS.get(r.get("bureau"), ("", ""))[1],
                           email=r.get("email") or EMAIL.get(r.get("bureau"), "")) for r in o.get("referrals") or []]
    for d in o.get("duplications") or []:
        d.setdefault("intent_to_abolish", o.get("intent_to_abolish", False))
    return o


def grade(bid, out, checks=None):
    from agents import grading
    b = load()[0].get(bid) or {}
    kind = out.get("source", "ai")
    rows = out.get("fiscal_rows") or []
    sourced = sum(1 for r in rows if r.get("provision") and r["provision"] != "None identified")
    return grading.finish([
        grading.text_test(b.get("text_source")),
        grading.prep_test(kind, checks),
        grading.share_test(sourced, len(rows), "fiscal items traced to a provision of the bill", "No fiscal item identified"),
        grading.open_test(len(out.get("reviewer_checks") or []), "the checklist"),
    ], kind)


# ---------------- Claude's run ----------------
def build_messages(bid, t_out, c_out, cost):
    from agents import llm
    draft = rule_draft(bid, t_out, c_out, cost)
    bills, secs = load()
    fin = [s for s in secs.get(bid, []) if re.search(r"appropriat|fund|compensation|salary|personnel|secretariat|transfer|abolish", s["heading"], re.I)]
    user = (f"TARGET: {bid} ({bills[bid]['label']}): {bills[bid]['title']}\n\n"
            f"TRAICE (Step 1, checked by the analyst): {json.dumps({k: t_out.get(k) for k in ('proposal', 'salient_features', 'related_measures_policy', 'fiscal_requirements')}, ensure_ascii=False)}\n\n"
            f"COMPAIRE (Step 2, checked by the analyst): {json.dumps({k: (c_out or {}).get(k) for k in ('memo_part', 'duplications', 'cost_notes')}, ensure_ascii=False)}\n\n"
            f"COST ENGINE (figures you may quote; never compute your own): {json.dumps(draft['estimate'], ensure_ascii=False)}\n\n"
            f"BUREAU COVERAGE (agencies named in the bill, matched to the DBM directory's coverage lists): {json.dumps(coverage(bid), ensure_ascii=False)}\n\n"
            f"ACTCHECK DRAFT (made by code; improve it): {json.dumps({k: draft[k] for k in ('fiscal_rows', 'duplications', 'intent_to_abolish', 'recommendation', 'referrals', 'memo')}, ensure_ascii=False)}\n\n"
            "BILL SECTIONS ON FUNDING, STAFFING AND TRANSFERS:\n" + "\n".join(f"[{s['id']}] {s['heading']}: {' '.join(s['text'].split())[:1500]}" for s in fin))
    return llm.prompt("p3_appraise"), user, draft


def check_output(out, draft):
    """Every peso figure must come from the engine or the bill; options and bureaus from the fixed lists."""
    from agents.verify import check_citations
    allowed = set()
    for e in (draft["estimate"]["low"], draft["estimate"]["high"]):
        for k in ("ps", "mooe", "co", "total", "recurring"):
            allowed.add(peso(e[k]))
    checks = []
    text = json.dumps({k: out.get(k) for k in ("fiscal_rows", "memo")}, ensure_ascii=False)
    for m in re.findall(r"P[\d,.]+ (?:million|billion)", text):
        if m not in allowed and m not in json.dumps(draft, ensure_ascii=False):
            checks.append({"claim": "peso figure", "section": "", "quote": m, "check": "figure not produced by the cost engine or the bill"})
    if (out.get("recommendation") or {}).get("option") not in OPTIONS:
        checks.append({"claim": "recommendation", "section": "", "quote": str(out.get("recommendation")), "check": "unknown recommendation option"})
    for r in out.get("referrals") or []:
        if r.get("bureau") not in BUREAUS:
            checks.append({"claim": "referral", "section": "", "quote": str(r.get("bureau")), "check": "unknown DBM bureau"})
        elif str(r.get("bureau")).startswith("BMB-") and r["bureau"] not in {g["bureau"] for g in coverage(out.get("target", ""))}:
            checks.append({"claim": "referral", "section": "", "quote": r["bureau"],
                           "check": "no agency named in the bill is under this bureau's coverage"})
    for d in out.get("duplications") or []:
        if d.get("section") and d.get("quote"):
            checks += check_citations([{"claim": d.get("note", ""), "section": d["section"], "quote": d["quote"]}])
    for r in out.get("fiscal_rows") or []:
        if r.get("section_id") and r.get("quote"):
            checks += check_citations([{"claim": r.get("item", ""), "section": r["section_id"], "quote": r["quote"]}])
    if not checks:
        checks.append({"claim": "figures and lists", "section": "", "quote": "", "check": "verified"})
    return checks
