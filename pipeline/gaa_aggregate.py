"""Aggregate the FY 2026 GAA by-object file (DBM, FY2026-GAA-Byobject.xlsx, amounts in thousand pesos)
into one row per agency: Personnel Services (ps), MOOE (mooe), Capital Outlays (co) and Financial Expenses
(finex), each split by program level: General Administration and Support (gas), Support to Operations (sto)
and Operations (ops). Also totals of regular and casual/contractual salaries.

Usage:  python -m pipeline.gaa_aggregate <FY2026-GAA-Byobject.xlsx> data/benchmarks/gaa_2026_by_agency.csv
Check:  the column totals add up to P6,793.162 billion, the FY 2026 GAA total in the DBM 2027 BPF briefer.
"""
import openpyxl, csv, collections, time, sys
t=time.time()
ws=openpyxl.load_workbook(sys.argv[1],read_only=True).worksheets[0]
agg=collections.defaultdict(float); names={}
CLS={'Personnel Services':'ps','Maintenance and Other Operating Expenses':'mooe','Capital Outlays':'co','Financial Expenses':'finex'}
LVL={'1':'gas','2':'sto','3':'ops'}
for r in ws.iter_rows(min_row=2,values_only=True):
    amt=r[19]
    try: amt=float(str(amt).replace(',','')) if amt not in (None,'') else 0
    except ValueError: amt=0
    if not amt: continue
    key=(r[1],r[3]); names[key]=(r[2],r[4])
    agg[(key,CLS.get(r[16],'other')+'_'+LVL.get(str(r[5])[:1],'other'))]+=amt
    if r[17]=='5010101000': agg[(key,'sal_regular')]+=amt
    if r[17]=='5010102000': agg[(key,'sal_casual')]+=amt
cols=[c+'_'+l for c in ('ps','mooe','co','finex','other') for l in ('gas','sto','ops','other')]+['sal_regular','sal_casual']
with open(sys.argv[2],"w",newline="") as f:
    w=csv.writer(f); w.writerow(['dept_code','department','agency_code','agency']+cols)
    for key,(dn,an) in sorted(names.items()):
        w.writerow([key[0],dn,key[1],an]+[round(agg.get((key,c),0)) for c in cols])
print("done",len(names),round(time.time()-t))
