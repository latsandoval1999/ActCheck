"""Build data/processed/bills.jsonl and sections.jsonl from data/raw_text.

Usage:  python -m pipeline.build_corpus
Input:  data/raw_text/<family folder>/[<NNth Congress>/]<file>.txt, mirroring
        "PP5538 Bill Corpus" (text from pdftotext or OCR).
Output: one record per document and one per section, with stable IDs such as
        "HB-20-2322", "HB-20-2322:s13", "RA-8435:s45", "CR-20-AGRICOM".
"""
import json
import re
from pathlib import Path

from pipeline.sections import parse_bill
from pipeline.extract import facts, laws_cited, substitution_list

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw_text"
OUT = ROOT / "data" / "processed"

# History folder files belong to these families (19th Congress versions)
HISTORY_FAMILY = {"HBT9663": "Department of Water Resources", "HB03670": "Department of Water Resources",
                  "HB03226": "Department of Water Resources", "SB102": "Department of Water Resources",
                  "SB87": "Department of Water Resources", "SB369": "Department of Fisheries and Aquatic Resources",
                  "SB614": "Department of Fisheries and Aquatic Resources", "HB03989": "Department of Fisheries and Aquatic Resources",
                  "HB04396": "Department of Fisheries and Aquatic Resources"}
LAW_NAME = [(re.compile(r"(?:Republic Act|R\.?\s?A\.?)\s*(?:No\.?)?\s*(\d+)", re.I), "RA-{}"),
            (re.compile(r"(?:Presidential Decree|P\.?\s?D\.?)\s*(?:No\.?)?\s*(\d+)", re.I), "PD-{}"),
            (re.compile(r"Executive Order\s*(?:No\.?)?\s*(\d+)", re.I), "EO-{}")]
EO_YEARS = {"22": "2023", "292": "1987"}


def law_id(stem):
    if re.match(r"^(RA|PD|BP|CA|EO|ACT)-", stem):
        return stem
    for rx, fmt in LAW_NAME:
        m = rx.search(stem)
        if m:
            lid = fmt.format(m.group(1))
            if lid.startswith("EO-") and m.group(1) in EO_YEARS:
                lid += "-" + EO_YEARS[m.group(1)]
            return lid
    return re.sub(r"[^A-Za-z0-9]+", "-", stem).strip("-")


def classify(path):
    """Return dict with id, label, chamber, congress, family, kind for a text file."""
    rel = path.relative_to(RAW)
    top = rel.parts[0]
    family = re.sub(r"^\d+\s+", "", top)
    congress = None
    for part in rel.parts[1:-1]:
        m = re.match(r"(\d{2})th Congress", part)
        if m:
            congress = m.group(1)
    stem = path.stem
    if family.lower().startswith("existing law"):
        lid = law_id(stem)
        return {"id": lid, "label": lid.replace("-", " ", 1), "chamber": "law", "congress": None, "family": "Existing law", "kind": "law"}
    if top == "_watch":
        family = "New measures (watcher)"
    if family.lower() == "history":
        family = HISTORY_FAMILY.get(stem, "History")
        congress = congress or "19"
    congress = congress or "20"
    if "committee report" in stem.lower():
        slug = re.sub(r"[^A-Za-z0-9]+", "-", family).strip("-")[:40]
        return {"id": f"CR-{congress}-{slug}", "label": f"Committee report ({family})", "chamber": "report",
                "congress": congress, "family": family, "kind": "committee_report"}
    m = re.match(r"(HBT|HB|SBT|SB)0*(\d+)", stem, re.I)
    if not m:
        sid = re.sub(r"[^A-Za-z0-9]+", "-", stem).strip("-")
        return {"id": f"DOC-{congress}-{sid}", "label": stem, "chamber": "other", "congress": congress, "family": family, "kind": "other"}
    kind, num = m.group(1).upper(), m.group(2)
    chamber = "SB" if kind.startswith("SB") else "HB"
    substitute = kind.endswith("T")
    return {"id": f"{chamber}-{congress}-{num}", "label": f"{chamber} {num}" + (" (substitute)" if substitute else ""),
            "chamber": chamber, "congress": congress, "family": family, "kind": "substitute" if substitute else "bill"}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    ocr_list = set((ROOT / "data" / "ocr_files.txt").read_text().split()) if (ROOT / "data" / "ocr_files.txt").exists() else set()
    docs, secs, seen = [], [], set()
    for p in sorted(RAW.rglob("*.txt")):
        if p.name.startswith("_") or re.search(r"\(\d\)$", p.stem):
            continue  # helper files and browser duplicates like "HB02538 (1)"
        meta = classify(p)
        if meta["id"] in seen:
            continue
        seen.add(meta["id"])
        raw = p.read_text(errors="ignore")
        parsed = parse_bill(raw)
        if meta["kind"] == "substitute" or (meta["kind"] == "bill" and substitution_list(raw[:6000])):
            meta["kind"] = "substitute"
        rec = {**meta, "is_law": meta["kind"] == "law", "is_history": meta["congress"] not in (None, "20"),
               "text_source": "ocr" if p.stem in ocr_list else "pdf_text", "file": str(p.relative_to(ROOT)),
               "title": parsed["title"], "n_sections": parsed["n_sections"],
               "explanatory_note": parsed["explanatory_note"][:6000], "front_matter": " ".join(raw[:raw.find("Be it enacted") if "Be it enacted" in raw else 1500].split())[:1500],
               "facts": facts(parsed["sections"]),
               "laws_cited": laws_cited(raw), "substitutes": substitution_list(raw[:20000], meta["congress"])}
        docs.append(rec)
        for s in parsed["sections"]:
            secs.append({"id": f"{meta['id']}:s{s['no']}", "bill": meta["id"], "no": s["no"], "heading": s["heading"], "text": s["text"]})
    with open(OUT / "bills.jsonl", "w") as f:
        for d in docs:
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
    with open(OUT / "sections.jsonl", "w") as f:
        for s in secs:
            f.write(json.dumps(s, ensure_ascii=False) + "\n")
    weak = [d["label"] for d in docs if d["kind"] in ("bill", "substitute") and d["n_sections"] < 3]
    print(f"{len(docs)} documents, {len(secs)} sections")
    if weak:
        print(f"{len(weak)} bills with fewer than 3 sections (check text quality): {', '.join(weak[:30])}")


if __name__ == "__main__":
    main()
