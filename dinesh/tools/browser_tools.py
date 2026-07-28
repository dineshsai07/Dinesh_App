"""Browser automation via Playwright."""

import threading
from typing import Optional

_browser = None
_page = None
_lock = threading.Lock()
_playwright = None


def _ensure_browser():
    global _browser, _page, _playwright
    with _lock:
        if _page is not None:
            return _page
        from playwright.sync_api import sync_playwright
        _playwright = sync_playwright().start()
        _browser = _playwright.chromium.launch(headless=False)
        _page = _browser.new_page()
        return _page


def browser_open_url(url: str) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    page = _ensure_browser()
    page.goto(url, wait_until="domcontentloaded", timeout=30000)
    title = page.title()
    return f"Opened {url} — page title: {title}."


def browser_click(selector: str) -> str:
    page = _ensure_browser()
    page.click(selector, timeout=10000)
    return f"Clicked element: {selector}."


def browser_type(selector: str, text: str, submit: bool = False) -> str:
    page = _ensure_browser()
    page.fill(selector, text)
    if submit:
        page.press(selector, "Enter")
    return f"Typed into {selector}." + (" Submitted." if submit else "")


def browser_read_page(max_chars: int = 3000) -> str:
    page = _ensure_browser()
    title = page.title()
    url = page.url
    try:
        body = page.inner_text("body")
    except Exception:
        body = page.content()[:max_chars]
    body = " ".join(body.split())[:max_chars]
    return f"URL: {url}\nTitle: {title}\nContent: {body}"


def browser_screenshot(filename: str = "browser.png") -> str:
    from config import ensure_screenshot_dir
    page = _ensure_browser()
    path = str(ensure_screenshot_dir() / filename)
    page.screenshot(path=path, full_page=False)
    return path


def browser_go_back() -> str:
    page = _ensure_browser()
    page.go_back()
    return f"Navigated back to {page.url}."


def browser_search(query: str) -> str:
    return browser_open_url(f"https://duckduckgo.com/?q={query.replace(' ', '+')}")


def browser_close() -> str:
    global _browser, _page, _playwright
    with _lock:
        try:
            if _browser:
                _browser.close()
            if _playwright:
                _playwright.stop()
        except Exception:
            pass
        _browser = _page = _playwright = None
    return "Browser closed."
