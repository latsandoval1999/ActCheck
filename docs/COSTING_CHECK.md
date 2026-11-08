# Costing figures checked against COA reports (preliminary, 8 Nov 2026)

Scope: the ten comparator rows in `data/benchmarks/coa_comparators.csv` were checked against the text of the COA Annual
Audit Report executive summaries in the author's folder, and the benefit rates in `agents/costing.py` against DBM
issuances. Preliminary: a reviewer should confirm before any figure is used outside the prototype.

## 1. Comparator agencies

All peso and staffing figures in the table match the COA executive summaries. The problems were in what the
numbers include, which matters because the engine divides obligations by staff:

| Agency (year) | Figures | Finding | Fix |
|---|---|---|---|
| DMW (2023) | Match: P4,374,805,000 appropriations; P3,218,697,520.22 obligations; 1,728 positions, 720 filled, 483 JO/COS | Obligations include the Aksyon Fund (P588,963,319.99 obligated of P1.2B) and the OFW Hospital, which are programs, not running costs | Added `obligations_operating` = P2,629,734,200.23 (excludes the Aksyon Fund); per-staff benchmark P2.68M → P2.19M |
| DHSUD (2020) | Match: P397.35M appropriations; 552 personnel | 552 = 315 permanent + 237 COS, not 552 regular positions | Split recorded; the "department" headcount default (552) is noted as including COS |
| DHSUD (2021) | Match: P691.69M; P689.35M obligated; 793 personnel | 793 = 626 permanent + 167 COS; appropriations exclude P14.76M continuing | Split and note recorded |
| DHSUD (2022) | Match: P1,012.59M; P934.97M obligated; 912 personnel | 721 plantilla + 191 COS | Split recorded |
| NWRB (2025) | Match: P286.20M; P270.03M obligated; 124 positions, 110 filled | COS staff not reported, so per-staff cost may be overstated | Note added |
| BFAR (2025) | Match (report in thousand pesos) | Also has 4,352 COS/JO (6,253 personnel in total); program-heavy | Personnel added; not used for per-staff benchmarks |
| CCC (2025) | Match: P271.49M; P260.01M obligated; 76 positions, 62 filled | Total personnel 186 (62 + 124 COS) was missing, so the engine divided by 76 positions | Personnel 186 added; per-staff benchmark P3.42M → P1.40M |
| CDA (2025) | Match: P1,110.88M; P1,213.86M obligated; 918 personnel | Obligations include P266.7M continuing appropriations | Note added |
| OCD (2025) | Match: P3,106.06M allotment; P2,415.35M obligated | 660 permanent + 373 JO/COS was missing; program-heavy (disaster response) | Personnel added; not used for per-staff benchmarks |
| PSC (2025) | Match: P1,293.64M; P2,697.15M obligated; 452 manpower | Obligations include P1.87B continuing appropriations and sports program funds | Note added; not used for per-staff benchmarks |

## 2. Benefit rates (per person per year, on top of basic salary)

| Item | Engine | Check |
|---|---|---|
| 2026 salary schedule | NBC No. 601 | Confirmed: third tranche under EO 64 s. 2024, effective 1 Jan 2026 |
| Mid-year and year-end bonus | 1 month each | Confirmed (RA 11466) |
| Cash gift | P5,000 | Confirmed |
| PERA | P2,000/month | Confirmed, unchanged in 2026 |
| Clothing/uniform allowance | P7,000/year | Confirmed |
| PEI | P5,000/year | Confirmed for 2025 (DBM Circular Letter 2025-13); needs yearly authority |
| GSIS government share | 12% of basic | Confirmed (RA 8291) |
| PhilHealth government share | 2.5% of basic | Confirmed (5% shared equally, DBM CL 2024-3) but the P100,000 salary ceiling was missing: now capped at P2,500/month |
| ECC | P100/month | Consistent with GSIS Resolution No. 9 s. 2003 (P30 → P100) |
| Pag-IBIG government share | P200/month | Consistent with the P10,000 maximum fund salary; HDMF circular not checked (to verify) |
| **Medical allowance** | missing | **Added**: up to P7,000/year from FY 2025 (EO 64 s. 2024; DBM BC 2024-6) |
| Service Recognition Incentive | not included | Left out on purpose: P20,000 only when authorized by an Administrative Order |

## 3. Effect on the cost ranges

| Bill | Before | After |
|---|---|---|
| HB 2322 (AGRICOM, commission) | P67.0M – P424.2M | P67.7M – P270.0M |
| HB 6789 (department) | P359.9M – P4.62B | P359.9M – P3.78B |

The upper bounds fall because the commission and department benchmarks no longer spread program funds over too few
people. Method B remains an upper bound: even "operating" obligations include some program spending.

## 4. Still to confirm

- NWRB contract-of-service headcount (not in the executive summary; see the full audit report).
- Pag-IBIG government share against the current HDMF circular.
- Whether the PEI and SRI will be authorized for 2026.
- MOOE share (35–60% of personnel cost) and average staff salary grade (SG 13–18) against GAA 2026 lines of comparable agencies.
