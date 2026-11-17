"""Show a bill's sections with the paragraph breaks of the source PDF (the stored sections are single lines of text).

The bill's text file keeps the PDF's line and paragraph breaks. Lines are joined back into paragraphs; blank lines
that fall in the middle of a sentence (page breaks, scanning gaps) are ignored; enumerated items such as (a), (1)
or a. start their own paragraph. Each section then takes the paragraphs from its own heading up to the next one.
"""
import re
from functools import lru_cache
from html import escape
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ITEM = re.compile(r"^\s*(\(?[a-z]{1,3}\)|\(?\d{1,2}\)|\d{1,2}\.(?!\d)|[a-z]\.\s|[ivx]{1,4}\.)\s*", re.I)
PAGE = re.compile(r"^\s*(=+\s*\[page \d+\]\s*=+|-?\s*\d{1,3}\s*-?|page \d+( of \d+)?)\s*$", re.I)


def _norm(s):
    return re.sub(r"[^a-z0-9]", "", s.lower())


@lru_cache(maxsize=64)
def paragraphs(path):
    p = ROOT / path if path else None
    if not p or not p.exists():
        return ()
    blocks, cur = [], []
    for line in p.read_text(errors="ignore").splitlines():
        if PAGE.match(line):
            continue
        s = line.strip()
        if not s:
            if cur:
                blocks.append(cur)
                cur = []
            continue
        if cur and (ITEM.match(s) or re.match(r"^(SEC(TION)?\.?\s*\d+|ARTICLE|CHAPTER|TITLE)\b", s)):
            blocks.append(cur)                     # a new item or section starts on its own line
            cur = []
        cur.append(s)
    if cur:
        blocks.append(cur)
    out = []
    for b in blocks:
        text = ""
        for ln in b:
            text = (text + ln) if text.endswith("-") and ln[:1].islower() else (f"{text} {ln}" if text else ln)
        # a blank line inside a sentence: join with the paragraph before
        mid = out and not re.search(r"[.:;!?\"”')]$", out[-1]) and (text[:1].islower() or re.search(r"[a-z,]$", out[-1]))
        if mid and not ITEM.match(text) and not re.match(r"^(SEC(TION)?\.?\s*\d+|ARTICLE|CHAPTER|TITLE)\b", text):
            out[-1] = f"{out[-1]} {text}"
        else:
            out.append(text)
    return tuple(out)


def section_paragraphs(path, sec_text, next_text=""):
    paras = paragraphs(path)
    key, nkey = _norm(sec_text)[:60], _norm(next_text)[:60]
    start = next((i for i, p in enumerate(paras) if key and key[:40] in _norm(p)), None)
    if start is None:
        return _split(sec_text)
    end = next((j for j in range(start + 1, len(paras)) if nkey and nkey[:40] in _norm(paras[j])), None)
    chunk = list(paras[start:end if end else min(len(paras), start + 60)])
    # keep the section to the length stored (the last section may run into signatures or annexes)
    total, keep = 0, []
    for p in chunk:
        keep.append(p)
        total += len(_norm(p))
        if total >= len(_norm(sec_text)) * 1.15:
            break
    if sum(1 for p in keep if len(p) <= 4) >= 2:            # labels and text in separate columns (some scans)
        return _split(sec_text)
    return keep or _split(sec_text)


def _split(text):
    """Fallback: break a one-line section before enumerated items."""
    parts = re.split(r"\s(?=\(?[a-z0-9]{1,3}\)\s[A-Za-z]{3})|(?<=;)\s(?=[A-Z(])|(?<=:)\s(?=(?:\(?[a-z0-9]{1,2}\)\s?)+[A-Z])", text)
    parts = [re.sub(r"^(?:\(?[a-z0-9]{1,2}\)\s*){2,}", "", p or "").strip() for p in parts]   # stray label runs
    return [p for p in parts if p]


def html(paras):
    out = []
    for p in paras:
        cls = "item" if ITEM.match(p) and not re.match(r"^SEC", p, re.I) else ""
        out.append(f'<p class="{cls}">{escape(p)}</p>')
    return f'<div class="ac-fulltext">{"".join(out)}</div>'
