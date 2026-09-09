"""ActionExecutor: raw Playwright actions with timeouts → structured results."""

from __future__ import annotations

from playwright.sync_api import Page

from tau_agent.webhermes.browser.results import ActionResult, run

DEFAULT_TIMEOUT_MS = 10_000


class ActionExecutor:
    """Thin deterministic wrapper over raw Playwright actions (components build on this)."""

    def __init__(self, page: Page, timeout_ms: int = DEFAULT_TIMEOUT_MS) -> None:
        self._page = page
        self._timeout = timeout_ms

    def click(self, selector: str) -> ActionResult:
        return run("click", lambda: self._page.click(selector, timeout=self._timeout))

    def fill(self, selector: str, value: str) -> ActionResult:
        return run("fill", lambda: self._page.fill(selector, value, timeout=self._timeout))

    def read_text(self, selector: str) -> ActionResult:
        res = run("read_text", lambda: self._page.text_content(selector, timeout=self._timeout))
        if res.ok and res.value is None:
            return ActionResult(ok=True, action="read_text", value="", duration_ms=res.duration_ms)
        return res

    def wait_for(self, selector: str, state: str = "visible") -> ActionResult:
        return run(
            "wait_for",
            lambda: self._page.wait_for_selector(selector, state=state, timeout=self._timeout),
        )

    def select(self, selector: str, value: str) -> ActionResult:
        return run(
            "select", lambda: self._page.select_option(selector, value, timeout=self._timeout)
        )

    def download(self, selector: str, save_as: str) -> ActionResult:
        """Click `selector`, catch the download event, save to `save_as`."""

        def _go() -> str:
            with self._page.expect_download(timeout=self._timeout) as dl:
                self._page.click(selector, timeout=self._timeout)
            dl.value.save_as(save_as)
            return save_as

        return run("download", _go)
