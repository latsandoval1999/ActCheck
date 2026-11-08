"""TrAIce (Agent 1): Evidence and Research.

Pipeline for one target bill:
  1. Profile    -- title, entity proposed, laws it cites, bills it substitutes (rules, no AI)
  2. Gather     -- related bills in the corpus (full text), related bills anywhere in the
                   18th-20th Congress (titles, Open Congress index), existing laws (law index)
  3. Baseline   -- rule-based relationship labels (the non-AI comparator)
  4. Agent      -- the model reads the evidence pack and labels each relationship, citing a
                   section ("HB-20-2322:s5"), a bill title ("meta:HB-19-9663") or a law title
                   ("law:RA-8435") with a verbatim quote
  5. Verify     -- every citation and quote is checked against the source; unverified claims
                   are flagged, not silently kept

Run from the command line (baseline only, no key needed):
    python -m agents.research HB-20-2322
"""
import json
import re
import sys
from functools import lru_cache
from pathlib import Path

import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from pipeline.compare import load, related_bills

ROOT = Path(__file__).resolve().parents[1]
PROC = ROOT / "data" / "processed"

ENTITY = re.compile(r"(?:CREATING|ESTABLISHING|CREATION OF|ESTABLISHMENT OF)\s+(?:THE\s+|AN?\s+)?(.{5,120}?)(?=,|\s+TO\s|\s+DEFINING|\s+PROVIDING|\s+APPROPRIATING|\s+AND\s+FOR|\s+PRESCRIBING|\s+UNDER\s|$)", re.I)
STOP_ENTITY = {"PHILIPPINE", "PHILIPPINES", "NATIONAL", "OF", "THE", "AND", "FOR", "ON", "IN", "TO", "A", "AN",
               "DEPARTMENT", "COMMISSION", "BUREAU", "OFFICE", "COUNCIL", "AUTHORITY", "BOARD", "AGENCY", "CENTER"}


# ---------------- indexes ----------------
@lru_cache(maxsize=1)
def bill_index():
    p = PROC / "bill_index.csv.gz"
    return pd.read_csv(p, dtype=str).fillna("") if p.exists() else pd.DataFrame(columns=["id", "title"])


@lru_cache(maxsize=1)
def law_index():
    p = PROC / "law_index.csv.gz"
    return pd.read_csv(p, dtype=str).fillna("") if p.exists() else pd.DataFrame(columns=["id", "title"])


@lru_cache(maxsize=1)
def _bill_title_model():
    bi = bill_index()
    texts = (bi["short_title"] + " " + bi["title"]).str.lower().tolist()
    vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=1, sublinear_tf=True)
    return vec, vec.fit_transform(texts)


@lru_cache(maxsize=1)
def _law_title_model():
    li = law_index()
    vec = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), min_df=1, sublinear_tf=True)
    return vec, vec.fit_transform(li["title"].str.lower().tolist())


# ---------------- step 1: profile ----------------
def entity_name(title):
    m = ENTITY.search(title or "")
    return " ".join(m.group(1).split()).strip(" ,") if m else ""


def profile(bid):
    bills, secs = load()
    b = bills[bid]
    li = law_index().set_index("id") if len(law_index()) else None
    cited = []
    for lid, n in (b.get("laws_cited") or {}).items():
        title = ""
        if li is not None:
            if lid in li.index:
                title = li.loc[lid, "title"]
            elif lid.startswith("EO-") and lid.count("-") == 1:  # EO without year: list candidates
                cands = li[li.index.str.startswith(lid + "-")]
                title = "; ".join(f"{i} {t[:60]}" for i, t in cands["title"].head(3).items())
        cited.append({"law": lid, "mentions": n, "title": title})
    return {"id": bid, "label": b["label"], "congress": b["congress"], "family": b["family"], "kind": b["kind"],
            "title": b["title"], "entity": entity_name(b["title"]), "text_source": b["text_source"],
            "n_sections": b["n_sections"], "laws_cited": cited, "substitutes": b.get("substitutes", [])}


# ---------------- step 2: gather ----------------
def metadata_history(bid, title, top=15, min_sim=0.30):
    """Similar bill titles across the 18th-20th Congress, including bills not in the corpus."""
    bi = bill_index()
    if not len(bi) or not title:
        return []
    vec, X = _bill_title_model()
    sims = cosine_similarity(vec.transform([title.lower()]), X).ravel()
    order = sims.argsort()[::-1]
    bills, _ = load()
    out = []
    for i in order[: top * 3]:
        r = bi.iloc[i]
        if r["id"] == bid or sims[i] < min_sim:
            continue
        out.append({"id": r["id"], "congress": r["congress"], "date_filed": r["date_filed"],
                    "title": (r["short_title"] + ": " if r["short_title"] else "") + r["title"],
                    "status": r["status"], "title_similarity": round(float(sims[i]), 3), "in_corpus": r["id"] in bills})
        if len(out) >= top:
            break
    return out


def law_candidates(bid, prof, top=8):
    """Existing laws: those the bill cites, plus laws whose titles resemble the entity or mandate."""
    li = law_index()
    out, seen = [], set()
    for c in prof["laws_cited"][:12]:
        out.append({"law": c["law"], "title": c["title"], "why": f"cited {c['mentions']}x in the bill", "score": None})
        seen.add(c["law"])
    if len(li):
        q = (prof["entity"] + " " + prof["entity"] + " " + prof["title"]).lower()
        keys = [w.lower() for w in re.findall(r"[A-Za-z]+", prof["entity"]) if w.upper() not in STOP_ENTITY and len(w) > 3]
        vec, X = _law_title_model()
        sims = cosine_similarity(vec.transform([q]), X).ravel()
        for i in sims.argsort()[::-1][: top * 6]:
            r = li.iloc[i]
            if r["id"] in seen or sims[i] < 0.15:
                continue
            if keys and not any(k in r["title"].lower() for k in keys):
                continue  # must share a subject word with the proposed entity
            out.append({"law": r["id"], "title": r["title"], "why": "title resembles the bill", "score": round(float(sims[i]), 3)})
            seen.add(r["id"])
            if len(out) >= len(prof["laws_cited"][:12]) + top:
                break
    bills, _ = load()
    for o in out:
        o["text_in_corpus"] = o["law"] in bills
    return out


# ---------------- step 3: baseline labels ----------------
def baseline_label(target, cand_id, sim, cand_congress, subs, same_family):
    """Rule-based relationship label; the comparator the agent must beat."""
    if cand_id in subs:
        return "consolidated into this substitute"
    other_chamber = cand_id.split("-")[0] != target["id"].split("-")[0]
    if cand_id.split("-")[1] == target["congress"] and sim >= 0.85:
        return "counterpart in other chamber (near-identical text)" if other_chamber else "refiled near-copy"
    if cand_congress and target["congress"] and int(cand_congress) < int(target["congress"]) and sim >= 0.5:
        return "earlier version"
    if other_chamber and cand_congress == target["congress"] and sim >= 0.4:
        return "counterpart in other chamber"
    if same_family and sim >= 0.3:
        return "same subject (competing or related design)"
    return "possibly related"


def evidence_pack(bid):
    bills, _ = load()
    prof = profile(bid)
    # history needs an explicit look back: keep the top matches overall AND the top matches
    # from each earlier Congress, so near-identical current bills cannot crowd them out
    allc = [r for r in related_bills(bid, top=80) if r["similarity"] >= 0.2]
    corpus = allc[:12]
    for c in sorted({r["congress"] for r in allc if r["congress"] and r["congress"] < (prof["congress"] or "99")}):
        corpus += [r for r in allc if r["congress"] == c and r not in corpus][:4]
    meta_all = metadata_history(bid, prof["title"], top=60)
    meta = meta_all[:15]
    for c in sorted({m["congress"] for m in meta_all if m["congress"] < (prof["congress"] or "99")}):
        meta += [m for m in meta_all if m["congress"] == c and m not in meta][:4]
    laws = law_candidates(bid, prof)
    subs = set(prof["substitutes"])
    rel = []
    for r in corpus:
        rel.append({"id": r["id"], "source": "corpus text", "congress": r["congress"], "similarity": r["similarity"],
                    "title": r["title"][:200],
                    "baseline_label": baseline_label(prof, r["id"], r["similarity"], r["congress"], subs, r["family"] == prof["family"])})
    have = {x["id"] for x in rel}
    for m in meta:
        if m["id"] in have:
            continue
        rel.append({"id": m["id"], "source": "title only" + ("" if not m["in_corpus"] else " (text in corpus)"),
                    "congress": m["congress"], "similarity": m["title_similarity"], "title": m["title"][:200],
                    "status": m["status"], "date_filed": m["date_filed"],
                    "baseline_label": baseline_label(prof, m["id"], m["title_similarity"] * 0.8, m["congress"], subs, False)})
    for s in subs - {x["id"] for x in rel}:
        rel.append({"id": s, "source": "named in substitution clause", "congress": s.split("-")[1], "similarity": None,
                    "title": "", "baseline_label": "consolidated into this substitute"})
    return {"profile": prof, "related": rel, "laws": laws}


# ---------------- step 4: agent ----------------
def _law_citing_sections(bid):
    """Sections of a bill that name an existing law (so overlap claims can be checked)."""
    from pipeline.extract import LAW_REF
    _, secs = load()
    return [s["no"] for s in secs.get(bid, []) if LAW_REF.search(s["text"])]


def _front_matter(bid, n=700):
    bills, _ = load()
    b = bills[bid]
    if b["kind"] in ("committee_report", "substitute") and b.get("front_matter"):
        return f"FRONT MATTER of {bid} (cite as {bid}:note): {b['front_matter'][:n]}"
    return ""


def _context(pack, max_docs=8):
    from agents.pipeline_agents import _sections_block, _key_sections
    bid = pack["profile"]["id"]
    want = sorted(set(_key_sections(bid)) | set(_law_citing_sections(bid)))
    parts = [_sections_block(bid, only=want or None, limit=60)]
    corpus_ids = [r["id"] for r in pack["related"] if r["source"] == "corpus text"]
    for cid in corpus_ids[:max_docs]:
        fm = _front_matter(cid)
        parts.append((fm + "\n" if fm else "") + _sections_block(cid, only=_key_sections(cid) or None, limit=20))
    for cid in corpus_ids[max_docs:]:  # the rest: short-title section only, still citable
        parts.append(_sections_block(cid, only=[1, 2], limit=2))
    titles = [f"[meta:{r['id']}] ({r['congress']}th Congress, filed {r.get('date_filed', '')}, status: {r.get('status', '')}) {r['title']}"
              for r in pack["related"] if r["source"].startswith("title only")]
    laws = []
    for l in pack["laws"]:
        if l["text_in_corpus"]:
            parts.append(_sections_block(l["law"], limit=15))
        laws.append(f"[law:{l['law']}] {l['title']} ({l['why']})")
    return ("BILL AND LAW SECTIONS:\n" + "\n\n".join(parts) +
            "\n\nOTHER BILLS (TITLES ONLY, FROM OPEN CONGRESS DATA):\n" + "\n".join(titles) +
            "\n\nEXISTING LAWS (TITLES FROM THE LEGAL DOCUMENTS LIBRARY):\n" + "\n".join(laws))


def build_messages(bid, pack=None):
    """The exact system prompt and user message Agent 1 sends (also usable by hand in a chat)."""
    from agents import llm
    pack = pack or evidence_pack(bid)
    baseline = [{k: r[k] for k in ("id", "source", "similarity", "baseline_label")} for r in pack["related"]]
    user = (f"TARGET: {bid}\nPROFILE (rules, no AI): {json.dumps(pack['profile'], ensure_ascii=False)}\n"
            f"BASELINE LABELS (rules, no AI; may be wrong): {json.dumps(baseline)}\n\n{_context(pack)}")
    return llm.prompt("p1_research"), user, pack


def check_output(out):
    """Verify every citation in an Agent 1 JSON output (from the API or pasted from a chat)."""
    from agents.verify import check_citations as _cc, quote_found

    def check_citations(claims):
        bills, _ = load()
        res = []
        for c in claims:
            if c["section"].endswith(":note"):
                b = c["section"].rsplit(":", 1)[0]
                ok = b in bills and quote_found(c["quote"], bills[b].get("front_matter", "") + " " + bills[b].get("explanatory_note", ""))
                res.append({**c, "check": "verified" if ok else ("quote not found in section" if b in bills else "section does not exist")})
            else:
                res += _cc([c])
        return res
    claims = [{"claim": r.get("basis", ""), "section": r.get("section", ""), "quote": r.get("quote", "")}
              for r in out.get("related", [])]
    claims += [{"claim": r.get("overlap", ""), "section": r.get("section", ""), "quote": r.get("quote", "")}
               for r in out.get("existing_law_overlaps", [])]
    return check_citations(claims)


def run_agent(bid):
    from agents import llm
    system, user, pack = build_messages(bid)
    text, meta = llm.call("research", system, user, max_tokens=6000)
    out = llm.parse_json(text)
    return {"pack": pack, "output": out, "checks": check_output(out), "meta": meta}


# ---------------- output ----------------
def brief_markdown(pack, agent_output=None, checks=None):
    p = pack["profile"]
    lines = [f"# Evidence brief: {p['label']} ({p['congress']}th Congress)",
             "_AI-assisted preliminary research for DBM reviewer validation._" if agent_output else "_Baseline evidence pack (rules only, no AI)._",
             "", f"**Title:** {p['title']}", f"**Entity proposed:** {p['entity'] or 'not detected'}",
             f"**Text source:** {p['text_source']} ({p['n_sections']} sections)"]
    if p["substitutes"]:
        lines.append(f"**Substitutes (from its own text):** {', '.join(p['substitutes'])}")
    lines += ["", "## Related measures"]
    if agent_output:
        verified = {(c['section'], c['quote']): c['check'] for c in (checks or [])}
        for r in agent_output.get("related", []):
            v = verified.get((r.get("section", ""), r.get("quote", "")), "unchecked")
            lines.append(f"- **{r.get('id')}**: {r.get('relationship')}. {r.get('basis', '')} "
                         f"[{r.get('section', '')}: \"{r.get('quote', '')}\"] *({v})*")
    else:
        for r in pack["related"][:20]:
            sim = f"{r['similarity']:.2f}" if r["similarity"] is not None else "n/a"
            lines.append(f"- **{r['id']}** ({r['source']}, similarity {sim}): {r['baseline_label']}. {r['title'][:120]}")
    lines += ["", "## Existing laws to check"]
    if agent_output and agent_output.get("existing_law_overlaps"):
        for o in agent_output["existing_law_overlaps"]:
            lines.append(f"- **{o.get('law')}**: {o.get('overlap')} [{o.get('section', '')}: \"{o.get('quote', '')}\"]")
    else:
        for l in pack["laws"]:
            lines.append(f"- **{l['law']}** ({l['why']}): {l['title'][:140]}")
    if agent_output and agent_output.get("gaps"):
        lines += ["", "## Gaps"] + [f"- {g}" for g in agent_output["gaps"]]
    return "\n".join(lines)


if __name__ == "__main__":
    # python -m agents.research HB-20-2322            -> baseline evidence brief
    # python -m agents.research HB-20-2322 --prompt   -> the full prompt, to paste into a chat by hand
    # python -m agents.research HB-20-2322 --check reply.json  -> verify a pasted agent reply
    args = sys.argv[1:]
    bid = args[0] if args and not args[0].startswith("--") else "HB-20-2322"
    if "--prompt" in args:
        system, user, _ = build_messages(bid)
        print("=== SYSTEM PROMPT ===\n" + system + "\n=== USER MESSAGE ===\n" + user)
    elif "--check" in args:
        from datetime import datetime, timezone
        from agents.llm import parse_json
        out = parse_json(open(args[args.index("--check") + 1]).read())
        checks = check_output(out)
        for c in checks:
            print(f"{c['check']:<28} {c['section']:<22} {c['quote'][:70]}")
        ok = sum(c["check"] == "verified" for c in checks)
        print(f"\n{ok} of {len(checks)} citations verified.")
        log = ROOT / "logs" / "p1_runs.jsonl"
        log.parent.mkdir(exist_ok=True)
        with open(log, "a") as f:
            f.write(json.dumps({"target": bid, "output": out, "checks": checks,
                                "meta": {"mode": "manual chat", "time": datetime.now(timezone.utc).isoformat(timespec="seconds")}},
                               ensure_ascii=False) + "\n")
        print(f"Saved to {log.relative_to(ROOT)} (used by: python3 -m eval.p1_eval --runs logs/p1_runs.jsonl)")
    else:
        print(brief_markdown(evidence_pack(bid)))
