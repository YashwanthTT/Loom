"""Research flow: web search → browse top sources in OUR browser → compose answer.

Built from existing primitives only (search + PageManager + adapter.ask).
Every stage calls `emit(line)` as it happens, so TUIs can stream progress.
No registry, no saved components — this is Q&A, not automation.
"""

from __future__ import annotations

from collections.abc import Callable

from playwright.sync_api import Page

from tau_agent.webhermes.browser.page import PageManager
from tau_agent.webhermes.search import web_search

_COMPOSE_SYSTEM = (
    "Answer the user's question using ONLY the browsed sources below. "
    "Be direct: lead with the answer (a list when asked for one), no preamble. "
    "If the sources lack the answer, say so in one line."
)
_MAX_SOURCE_CHARS = 6000


def research(
    task: str,
    *,
    page: Page,
    adapter,
    emit: Callable[[str], None] = print,
    max_sources: int = 2,
) -> str:
    """Run the full flow, streaming progress through `emit`. Returns the answer."""
    emit(f"searching the web for: {task}")
    try:
        hits = web_search(task)
    except RuntimeError as exc:
        return f"Search failed: {exc}"
    if not hits:
        return "No web results found."
    for i, h in enumerate(hits[:max_sources], 1):
        emit(f"[{i}] {h['title']}\n    {h['url']}")

    sources: list[str] = []
    pm = PageManager(page)
    for h in hits[:max_sources]:
        emit(f"browsing: {h['url']}")
        goto = pm.goto(h["url"])
        if not goto.ok:
            emit(f"  skipped ({goto.error_type}: {(goto.error or '')[:100]})")
            continue
        text = pm.body_text(_MAX_SOURCE_CHARS)
        if not text.ok or not (text.value or "").strip():
            emit("  skipped (no readable text)")
            continue
        emit(f"  read {len(text.value or '')} chars")
        sources.append(f"SOURCE {h['url']}:\n{text.value}")

    if not sources:
        return "Could not read any source."
    emit("composing the answer…")
    try:
        answer = adapter.ask(
            _COMPOSE_SYSTEM,
            f"Question: {task}\n\n" + "\n\n".join(sources),
            method="research",
            instruction=task[:200],
        )
    except Exception as exc:  # noqa: BLE001 — research never raises
        return f"Composing failed: {type(exc).__name__}: {exc}"
    emit(answer)
    return answer
