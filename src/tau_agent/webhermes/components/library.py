"""Initial library: 8 components with manually written locators, zero AI.

Each executes through the shared run() boundary on a live-resolved Locator —
the same path AI-discovered (spec-JSON) and manual (CSS) locators take.
Each declares how its success is verified (Phase 5 strategies).
"""

from __future__ import annotations

from typing import Any

from playwright.sync_api import Page

from tau_agent.webhermes.browser.actions import DEFAULT_TIMEOUT_MS
from tau_agent.webhermes.browser.page import PageManager
from tau_agent.webhermes.browser.results import ActionResult, run
from tau_agent.webhermes.components.base import BrowserComponent
from tau_agent.webhermes.components.verify import VerificationSpec


class Navigate(BrowserComponent):
    name = "navigate"
    description = "Go to a URL and wait for load."
    input_schema = {
        "type": "object",
        "required": ["url"],
        "properties": {"url": {"type": "string"}},
    }
    action = "navigate"

    def execute(self, page: Page, inputs: dict[str, Any]) -> ActionResult:
        values, err = self._checked("navigate", inputs, "url")
        if err is not None:
            return err
        assert values is not None
        return PageManager(page).goto(str(values["url"]))

    def _spec(self, inputs: dict[str, Any]) -> VerificationSpec:
        url = str(inputs.get("url", ""))
        return VerificationSpec("url_contains", {"expected": url}) if url else super()._spec(inputs)


class Click(BrowserComponent):
    name = "click"
    description = "Click the bound element."
    input_schema = {"type": "object", "required": []}
    action = "click"
    verification = VerificationSpec("exists", {})

    def execute(self, page: Page, inputs: dict[str, Any]) -> ActionResult:
        self._remember(inputs)
        return self._act("click", page, lambda t: t.click(timeout=DEFAULT_TIMEOUT_MS))

    def _spec(self, inputs: dict[str, Any]) -> VerificationSpec:
        return VerificationSpec("exists", {"selector": self.locator})


class Fill(BrowserComponent):
    name = "fill"
    description = "Fill the bound field with a value."
    input_schema = {
        "type": "object",
        "required": ["value"],
        "properties": {"value": {"type": "string"}},
    }
    action = "fill"

    def execute(self, page: Page, inputs: dict[str, Any]) -> ActionResult:
        values, err = self._checked("fill", inputs, "value")
        if err is not None:
            return err
        assert values is not None
        value = str(values["value"])
        return self._act("fill", page, lambda t: t.fill(value, timeout=DEFAULT_TIMEOUT_MS))

    def _spec(self, inputs: dict[str, Any]) -> VerificationSpec:
        return VerificationSpec(
            "input_value", {"selector": self.locator, "expected": str(inputs.get("value", ""))}
        )


class Search(BrowserComponent):
    name = "search"
    description = "Fill the bound input with a query and submit via a button."
    input_schema = {
        "type": "object",
        "required": ["query", "button"],
        "properties": {"query": {"type": "string"}, "button": {"type": "string"}},
    }
    action = "search"

    def execute(self, page: Page, inputs: dict[str, Any]) -> ActionResult:
        values, err = self._checked("search", inputs, "query", "button")
        if err is not None:
            return err
        assert values is not None
        filled = Fill(self.locator).execute(page, {"value": str(values["query"])})
        if not filled.ok:
            return filled
        return Click(str(values["button"])).execute(page, {})

    def _spec(self, inputs: dict[str, Any]) -> VerificationSpec:
        return VerificationSpec(
            "input_value", {"selector": self.locator, "expected": str(inputs.get("query", ""))}
        )


class Select(BrowserComponent):
    name = "select"
    description = "Choose an option in the bound dropdown."
    input_schema = {
        "type": "object",
        "required": ["value"],
        "properties": {"value": {"type": "string"}},
    }
    action = "select"

    def execute(self, page: Page, inputs: dict[str, Any]) -> ActionResult:
        values, err = self._checked("select", inputs, "value")
        if err is not None:
            return err
        assert values is not None
        value = str(values["value"])
        return self._act(
            "select", page, lambda t: t.select_option(value, timeout=DEFAULT_TIMEOUT_MS)
        )

    def _spec(self, inputs: dict[str, Any]) -> VerificationSpec:
        return VerificationSpec(
            "input_value", {"selector": self.locator, "expected": str(inputs.get("value", ""))}
        )


class Extract(BrowserComponent):
    name = "extract"
    description = "Read text from the bound element."
    input_schema = {"type": "object", "required": []}
    action = "extract"

    def execute(self, page: Page, inputs: dict[str, Any]) -> ActionResult:
        self._remember(inputs)
        res = self._act("extract", page, lambda t: t.text_content(timeout=DEFAULT_TIMEOUT_MS))
        if res.ok and res.value is None:
            return ActionResult(ok=True, action="extract", value="", duration_ms=res.duration_ms)
        return res

    def _spec(self, inputs: dict[str, Any]) -> VerificationSpec:
        return VerificationSpec("exists", {"selector": self.locator})


class Wait(BrowserComponent):
    name = "wait"
    description = "Wait for the bound element to reach a state."
    input_schema = {
        "type": "object",
        "required": [],
        "properties": {"state": {"type": "string"}},
    }
    action = "wait"

    def execute(self, page: Page, inputs: dict[str, Any]) -> ActionResult:
        self._remember(inputs)
        state = str(inputs.get("state", "visible"))
        return self._act(
            "wait", page, lambda t: t.wait_for(state=state, timeout=DEFAULT_TIMEOUT_MS)
        )

    def _spec(self, inputs: dict[str, Any]) -> VerificationSpec:
        return VerificationSpec("exists", {"selector": self.locator})


class Download(BrowserComponent):
    name = "download"
    description = "Click the bound element and save the triggered download."
    input_schema = {
        "type": "object",
        "required": ["save_as"],
        "properties": {"save_as": {"type": "string"}},
    }
    action = "download"

    def execute(self, page: Page, inputs: dict[str, Any]) -> ActionResult:
        values, err = self._checked("download", inputs, "save_as")
        if err is not None:
            return err
        assert values is not None
        save_as = str(values["save_as"])
        try:
            target = self._target(page)
        except Exception as exc:  # noqa: BLE001 — execute() never raises
            return ActionResult(
                ok=False,
                action="download",
                error=str(exc)[:500],
                error_type=type(exc).__name__,
            )

        def _go() -> str:
            with page.expect_download(timeout=DEFAULT_TIMEOUT_MS) as dl:
                target.click(timeout=DEFAULT_TIMEOUT_MS)
            dl.value.save_as(save_as)
            return save_as

        return run("download", _go)

    def _spec(self, inputs: dict[str, Any]) -> VerificationSpec:
        return VerificationSpec("file_exists", {"path": str(inputs.get("save_as", ""))})
