"""In-app web search: DuckDuckGo HTML endpoint over httpx, stdlib parsing.

No API keys, no new dependencies. `parse_ddg` is pure (unit-tested);
`web_search` is the thin network wrapper (tests monkeypatch httpx).
"""

from __future__ import annotations

from html.parser import HTMLParser

import httpx

_DDG_URL = "https://html.duckduckgo.com/html/"
_HEADERS = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"}


class _DDGParser(HTMLParser):
    """Pull (title, url, snippet) triples out of DDG's html endpoint."""

    def __init__(self) -> None:
        super().__init__()
        self.results: list[dict[str, str]] = []
        self._cur: dict[str, str] = {}
        self._in_title = False
        self._in_snippet = False
        self._snippet_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        cls = dict(attrs).get("class", "") or ""
        if tag == "a" and "result__a" in cls:
            self._cur = {"title": "", "url": dict(attrs).get("href", "") or "", "snippet": ""}
            self._in_title = True
        elif tag == "a" and "result__snippet" in cls:
            self._in_snippet = True
            self._snippet_depth = 0
        elif self._in_snippet:
            self._snippet_depth += 1

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_title:
            self._in_title = False
            if self._cur.get("url"):
                self.results.append(self._cur)
        elif tag == "a" and self._in_snippet and self._snippet_depth == 0:
            self._in_snippet = False
        elif self._in_snippet:
            self._snippet_depth = max(0, self._snippet_depth - 1)

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if not text:
            return
        if self._in_title and self._cur is not None:
            self._cur["title"] += " " + text if self._cur["title"] else text
        elif self._in_snippet and self.results:
            prev = self.results[-1]["snippet"]
            self.results[-1]["snippet"] = (prev + " " + text if prev else text).strip()


def parse_ddg(html: str) -> list[dict[str, str]]:
    """Parse DDG html into [{title, url, snippet}]."""
    parser = _DDGParser()
    parser.feed(html)
    return [r for r in parser.results if r["title"] and r["url"]]


def web_search(query: str, max_results: int = 5, timeout_s: float = 20.0) -> list[dict[str, str]]:
    """Search the web. Raises RuntimeError (never raw httpx) on failure."""
    try:
        resp = httpx.post(
            _DDG_URL, data={"q": query}, headers=_HEADERS, timeout=timeout_s, follow_redirects=True
        )
        resp.raise_for_status()
    except Exception as exc:  # noqa: BLE001 — boundary: convert, never leak
        raise RuntimeError(f"web search failed: {type(exc).__name__}: {exc}") from exc
    return parse_ddg(resp.text)[:max_results]
