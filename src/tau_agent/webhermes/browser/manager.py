"""BrowserManager: launch/close, contexts (cookies, viewport, user agent), sessions."""

from __future__ import annotations

from typing import Any

from playwright.sync_api import Browser, BrowserContext, Playwright, sync_playwright


class BrowserManager:
    """Owns one Chromium instance; sessions map ids to contexts (concurrency-ready)."""

    def __init__(self, headless: bool = True) -> None:
        self._headless = headless
        self._pw: Playwright | None = None
        self._browser: Browser | None = None
        self.sessions: dict[str, BrowserContext] = {}

    def start(self) -> None:
        self._pw = sync_playwright().start()
        self._browser = self._pw.chromium.launch(headless=self._headless)

    def stop(self) -> None:
        for ctx in self.sessions.values():
            ctx.close()
        self.sessions.clear()
        if self._browser is not None:
            self._browser.close()
            self._browser = None
        if self._pw is not None:
            self._pw.stop()
            self._pw = None

    def new_session(
        self,
        session_id: str,
        viewport: dict[str, int] | None = None,
        user_agent: str | None = None,
        cookies: list[dict[str, Any]] | None = None,
    ) -> BrowserContext:
        assert self._browser is not None, "call start() first"
        ctx = self._browser.new_context(viewport=viewport, user_agent=user_agent)
        if cookies:
            ctx.add_cookies(cookies)
        self.sessions[session_id] = ctx
        return ctx

    def close_session(self, session_id: str) -> None:
        ctx = self.sessions.pop(session_id, None)
        if ctx is not None:
            ctx.close()
