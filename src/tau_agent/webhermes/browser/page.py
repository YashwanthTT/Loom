"""PageManager: navigation + load states, screenshots, DOM snapshots, console/network logs."""

from __future__ import annotations

import json
from pathlib import Path

from playwright.sync_api import Page

from tau_agent.webhermes.browser.results import ActionResult, run

DEFAULT_TIMEOUT_MS = 10_000
_MAX_LOG_ENTRIES = 500


class PageManager:
    """Wraps one Playwright Page; all fallible ops return ActionResult."""

    def __init__(self, page: Page) -> None:
        self._page = page
        self._cdp = page.context.new_cdp_session(page)
        self.console: list[str] = []
        self.requests: list[dict[str, str]] = []
        page.on("console", lambda msg: self._append(self.console, f"{msg.type}: {msg.text}"))
        page.on(
            "request",
            lambda req: self._append(
                self.requests, {"method": req.method, "url": req.url, "status": ""}
            ),
        )
        page.on(
            "response",
            lambda res: self._append(
                self.requests,
                {"method": res.request.method, "url": res.url, "status": str(res.status)},
            ),
        )

    @staticmethod
    def _append(log: list, entry) -> None:
        if len(log) < _MAX_LOG_ENTRIES:
            log.append(entry)

    def goto(
        self, url: str, wait_until: str = "load", timeout_ms: int = DEFAULT_TIMEOUT_MS
    ) -> ActionResult:
        """Navigate with an explicit load-state wait (never rely on implicit timing)."""
        res = run("goto", lambda: self._page.goto(url, wait_until=wait_until, timeout=timeout_ms))
        if not res.ok:
            return res
        return run("goto", lambda: self._page.url)

    def screenshot(
        self, path: str | Path, full_page: bool = False, selector: str | None = None
    ) -> ActionResult:
        """Full-page or element-scoped screenshot saved to `path`."""
        dest = str(path)
        if selector:
            locator = self._page.locator(selector)
            return run(
                "screenshot",
                lambda: locator.screenshot(path=dest, timeout=DEFAULT_TIMEOUT_MS),
            )
        return run("screenshot", lambda: self._page.screenshot(path=dest, full_page=full_page))

    def body_text(self, max_chars: int = 8000) -> ActionResult:
        """Rendered body text (inner_text skips hidden/script noise), capped."""
        locator = self._page.locator("body")
        res = run("body_text", lambda: locator.inner_text(timeout=DEFAULT_TIMEOUT_MS))
        if res.ok and res.value is not None and len(res.value) > max_chars:
            return ActionResult(ok=True, action="body_text", value=res.value[:max_chars],
                                duration_ms=res.duration_ms)
        return res

    def dom_snapshot(self) -> ActionResult:
        """HTML + accessibility tree; value=HTML, extra['aria']=JSON tree."""
        try:
            html = self._page.content()
            aria = self._cdp.send("Accessibility.getFullAXTree")
        except Exception as exc:  # noqa: BLE001 — same boundary as run()
            return ActionResult(
                ok=False,
                action="dom_snapshot",
                error=str(exc)[:500],
                error_type=type(exc).__name__,
            )
        return ActionResult(
            ok=True, action="dom_snapshot", value=html, extra={"aria": json.dumps(aria)}
        )
