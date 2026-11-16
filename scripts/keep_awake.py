"""Open the ActCheck portal in a headless browser so Streamlit Community Cloud counts a visit, and wake the app
if it has gone to sleep (Streamlit puts apps to sleep after 12 hours without traffic). Run by
.github/workflows/keep-awake.yml every 6 hours until 31 December 2026."""
import sys
import time

from playwright.sync_api import sync_playwright

URL = "https://act-check.streamlit.app/"

with sync_playwright() as p:
    b = p.chromium.launch()
    page = b.new_page()
    page.goto(URL, timeout=120_000, wait_until="domcontentloaded")
    time.sleep(10)
    woke = False
    for frame in [page] + page.frames:
        btn = frame.get_by_role("button", name="Yes, get this app back up")
        if btn.count():
            btn.first.click()
            woke = True
            break
    # let the app start and the page connect, which is what counts as traffic
    time.sleep(90 if woke else 30)
    text = " ".join(f.inner_text("body") for f in page.frames if f.url.startswith("https://act-check"))[:4000] if page.frames else ""
    ok = "ActCheck" in text or "ActCheck" in page.title()
    print(f"woke={woke} loaded={ok} title={page.title()!r}")
    b.close()
    sys.exit(0 if ok or woke else 1)
