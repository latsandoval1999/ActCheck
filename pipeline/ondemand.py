"""Fetch one bill's text when a reviewer opens a bill that is listed but not yet in the corpus.

Uses the same sources and rules as the daily check (robots.txt respected, a descriptive user agent,
no bot-challenge bypass): the House documents server PDF, or the Senate bill record's PDF. The text is
saved under data/raw_text/_watch/<Congress>th Congress/, the corpus is rebuilt and caches are cleared.
On the hosted portal this needs poppler-utils (see packages.txt); scanned PDFs also need tesseract.
"""
import importlib
import urllib.error

from pipeline import watch

HOUSE_PDF = "https://docs.congress.hrep.online/legisdocs/basic_{c}/HB{n:05d}.pdf"


def _pdf_for(row):
    ch, c, n = row["id"].split("-")
    n = int(n)
    if ch == "SB":
        listing = watch.load_listing() if c == watch.CONGRESS else {}
        sid = (listing.get(n) or {}).get("system_id")
        if sid:
            return watch.senate_pdf(sid)
    url = row.get("source_url") or ""
    if ch == "HB" and not url.lower().endswith(".pdf"):
        url = HOUSE_PDF.format(c=c, n=n)
    if not url.lower().endswith(".pdf"):
        return None, "no PDF link known for this bill yet"
    if not watch.allowed(url):
        return None, "blocked by robots.txt"
    try:
        data = watch.http_get(url)
        return (data, url) if data.startswith(b"%PDF") else (None, "the source did not return a PDF")
    except urllib.error.HTTPError as e:
        return None, f"the source returned HTTP {e.code}"
    except Exception as e:
        return None, f"the source is unavailable ({type(e).__name__})"


def clear_caches():
    for name in ("pipeline.compare", "agents.research", "agents.verify", "agents.costing", "pipeline.catalogue", "agents.chat"):
        try:
            mod = importlib.import_module(name)
        except Exception:
            continue
        for obj in vars(mod).values():
            if callable(getattr(obj, "cache_clear", None)):
                obj.cache_clear()


def fetch(row):
    """Return (ok, message)."""
    data, info = _pdf_for(row)
    if data is None:
        return False, info
    text, method = watch.pdf_to_text(data)
    if method == "no_text" or len("".join(text.split())) < 300:
        return False, "the PDF has no text layer (scanned) and OCR is not available here; the daily check will OCR it"
    ch, c, n = row["id"].split("-")
    folder = watch.TEXT / f"{c}th Congress"
    folder.mkdir(parents=True, exist_ok=True)
    (folder / (f"HB{int(n):05d}.txt" if ch == "HB" else f"SB{n}.txt")).write_text(text)
    from pipeline import build_corpus
    build_corpus.main()
    clear_caches()
    return True, f"text read from {info} ({'OCR' if method == 'ocr' else 'PDF text'})"
