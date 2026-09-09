"""Search parser: deterministic on canned HTML. Network wrapped separately."""

from __future__ import annotations

import pytest

from tau_agent.webhermes.search import parse_ddg, web_search

HTML = """
<html><body>
<div class="result">
  <h2><a class="result__a" href="https://example.com/a">First Title</a></h2>
  <a class="result__snippet" href="https://example.com/a">The <b>snippet</b> one.</a>
</div>
<div class="result">
  <h2><a class="result__a" href="https://example.com/b">Second</a></h2>
  <a class="result__snippet" href="https://example.com/b">Snippet two.</a>
</div>
</body></html>
"""


def test_parse_ddg_extracts_triples() -> None:
    rows = parse_ddg(HTML)
    assert rows == [
        {"title": "First Title", "url": "https://example.com/a", "snippet": "The snippet one."},
        {"title": "Second", "url": "https://example.com/b", "snippet": "Snippet two."},
    ]


def test_parse_ddg_empty() -> None:
    assert parse_ddg("<html><body>nothing here</body></html>") == []


def test_web_search_uses_httpx(monkeypatch: pytest.MonkeyPatch) -> None:
    class _Resp:
        text = HTML

        def raise_for_status(self) -> None:
            pass

    monkeypatch.setattr("tau_agent.webhermes.search.httpx.post", lambda *a, **k: _Resp())
    rows = web_search("whatever")
    assert len(rows) == 2 and rows[0]["url"] == "https://example.com/a"


def test_web_search_failure_is_runtime_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def _boom(*a: object, **k: object) -> None:
        raise ConnectionError("dns down")

    monkeypatch.setattr("tau_agent.webhermes.search.httpx.post", _boom)
    with pytest.raises(RuntimeError, match="web search failed"):
        web_search("whatever")
