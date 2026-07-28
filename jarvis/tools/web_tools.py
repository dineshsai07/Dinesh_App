"""Web search + page fetch."""

from __future__ import annotations

import json
import re
import urllib.parse
from html.parser import HTMLParser
from urllib.request import Request, urlopen


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self._skip = False
        self.parts: list[str] = []

    def handle_starttag(self, tag, attrs):
        if tag in ("script", "style", "noscript"):
            self._skip = True

    def handle_endtag(self, tag):
        if tag in ("script", "style", "noscript"):
            self._skip = False

    def handle_data(self, data):
        if not self._skip:
            t = data.strip()
            if t:
                self.parts.append(t)


def _search_ddgs(query: str) -> list[dict]:
    try:
        from ddgs import DDGS
    except ImportError:
        try:
            from duckduckgo_search import DDGS
        except ImportError:
            return []
    try:
        with DDGS() as ddgs:
            return list(ddgs.text(query, max_results=5)) or []
    except Exception:
        return []


def _search_duckduckgo_api(query: str) -> list[dict]:
    """Instant Answer / related topics fallback (no scraping dependency)."""
    url = "https://api.duckduckgo.com/?" + urllib.parse.urlencode({
        "q": query,
        "format": "json",
        "no_redirect": 1,
        "no_html": 1,
    })
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 Dinesh/3.0"})
        with urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="replace"))
        out = []
        if data.get("AbstractText"):
            out.append({
                "title": data.get("Heading") or query,
                "body": data["AbstractText"],
                "href": data.get("AbstractURL") or "",
            })
        for topic in (data.get("RelatedTopics") or [])[:5]:
            if isinstance(topic, dict) and topic.get("Text"):
                out.append({
                    "title": topic.get("Text", "")[:80],
                    "body": topic.get("Text", ""),
                    "href": topic.get("FirstURL") or "",
                })
            elif isinstance(topic, dict) and "Topics" in topic:
                for t in topic["Topics"][:2]:
                    if t.get("Text"):
                        out.append({
                            "title": t["Text"][:80],
                            "body": t["Text"],
                            "href": t.get("FirstURL") or "",
                        })
        return out
    except Exception:
        return []


def web_search(query: str) -> str:
    results = _search_ddgs(query)
    if not results:
        results = _search_duckduckgo_api(query)
    if not results:
        return (
            f"Search returned no results for '{query}'. "
            "Network may be blocking search providers — try fetch_webpage with a known URL."
        )
    lines = []
    for r in results[:5]:
        title = r.get("title") or ""
        body = r.get("body") or ""
        href = r.get("href") or ""
        lines.append(f"- {title}: {body} ({href})" if href else f"- {title}: {body}")
    return "\n".join(lines)


def fetch_webpage(url: str, max_chars: int = 6000) -> str:
    if not url.startswith(("http://", "https://")):
        url = "https://" + url
    try:
        req = Request(url, headers={"User-Agent": "Mozilla/5.0 (Macintosh; Dinesh/3.0)"})
        with urlopen(req, timeout=20) as resp:
            raw = resp.read(500_000)
            charset = resp.headers.get_content_charset() or "utf-8"
            html = raw.decode(charset, errors="replace")
        parser = _TextExtractor()
        parser.feed(html)
        text = re.sub(r"\s+", " ", " ".join(parser.parts)).strip()
        if not text:
            return f"Page fetched but no readable text: {url}"
        if len(text) > max_chars:
            text = text[:max_chars] + " …[truncated]"
        return f"URL: {url}\nContent: {text}"
    except Exception as e:
        return f"Could not fetch {url}: {e}"
