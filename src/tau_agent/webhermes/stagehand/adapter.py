"""StagehandAdapter — the ONLY module allowed to touch AI browser understanding.

Deviation (explicit): the real `stagehand` PyPI package requires Browserbase +
first-party model keys and offers no custom OpenAI-compatible endpoint in its
Python SDK, so it cannot run on this repo's only subscription (OpenCode Go).
This adapter therefore implements the same three-primitive seam on top of the
already-proven `tau_ai` provider + Phase 1 snapshots. Swapping in the real SDK
later is a one-file change, which is exactly what this boundary is for.

Every call is logged as JSONL (instruction in, result out, latency, tokens —
cost is null: OpenCode Go publishes no per-model price; Phase 12 uses tokens +
latency + the logged `llm_calls_count`).
"""

from __future__ import annotations

import json
import os
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from anyio.from_thread import start_blocking_portal
from playwright.sync_api import Page

from tau_agent.messages import Usage, UserMessage
from tau_agent.provider_events import AssistantDoneEvent, AssistantErrorEvent
from tau_agent.webhermes.browser import ActionResult
from tau_agent.webhermes.browser.locators import locator_spec, resolve_locator
from tau_agent.webhermes.browser.page import PageManager
from tau_agent.webhermes.browser.results import run
from tau_agent.webhermes.config import WebHermesConfig, load_config
from tau_agent.webhermes.stagehand.real import RealStagehand
from tau_ai.openai_compatible import OpenAICompatibleProvider

LOG_PATH = Path(os.environ.get("WEBHERMES_LLM_LOG", "webhermes-llm-calls.jsonl"))
_MAX_AX_CHARS = 12_000


def default_backend() -> str:
    """Live read of STAGEHAND_BACKEND: 'real' (SDK over CDP) or 'snapshot' (own prompts)."""
    return os.environ.get("STAGEHAND_BACKEND", "snapshot").strip().lower()


def _ms(start: float) -> int:
    return int((time.monotonic() - start) * 1000)


_OBSERVE_SYSTEM = (
    "You locate one UI element on a web page. Reply with ONLY JSON, no fences. "
    'Priority: {"role": "<aria role>", "name": "<accessible name>"} first; '
    'else {"text": "<visible text>"} or {"placeholder": "<placeholder>"}; '
    'CSS {"css": "<selector>"} only as a last resort. '
    "NEVER use [name=...] or other attribute selectors: 'name' means the "
    "ACCESSIBLE name from the tree, matched via role locators, not CSS."
)
_ACT_SYSTEM = (
    "You turn a browser instruction into one action. Reply with ONLY JSON, no fences, "
    'e.g. {"action": "click", "target": {"role": "button", "name": "Search"}} or '
    '{"action": "fill", "target": {"role": "textbox", "name": "Query"}, "value": "x"}. '
    '<locator> MUST be {"role", "name"} when the tree shows a role and name; '
    '{"text"}/{"placeholder"} otherwise; {"css"} only if nothing else identifies it. '
    "NEVER use [name=...] or other attribute selectors."
)
_EXTRACT_SYSTEM = (
    "You extract structured data from a web page. "
    "Reply with ONLY the JSON object matching the given schema, no fences."
)


class StagehandAdapter:
    """Exactly three primitives; failures become ActionResults, never raw."""

    def __init__(self, config: WebHermesConfig | None = None) -> None:
        self._config = config or load_config()
        self._session_id = uuid4().hex
        self.calls_made = 0  # every LLM round-trip bumps this (Phase 12's metric)
        self._real_tokens = {"in": 0, "out": 0}  # accumulated by the real-backend hook
        self._real: RealStagehand | None = None
        # One background event loop for all LLM calls: Playwright's sync API
        # claims the main thread's loop, so asyncio has to live elsewhere.
        self._portal_cm = start_blocking_portal()
        self._portal = self._portal_cm.__enter__()

    def close(self) -> None:
        if self._real is not None:
            self._real.close()
            self._real = None
        self._portal_cm.__exit__(None, None, None)

    def _hook(self, text: str, usage) -> None:
        self.calls_made += 1
        self._real_tokens["in"] += usage.input
        self._real_tokens["out"] += usage.output

    def _real_backend(self) -> RealStagehand:
        if self._real is None:
            self._real = RealStagehand(self._portal, self._config, on_llm_call=self._hook)
        return self._real

    def _take(self) -> Usage:
        """Consume accumulated real-backend tokens as one Usage for the log line."""
        usage = Usage(input=self._real_tokens["in"], output=self._real_tokens["out"])
        self._real_tokens = {"in": 0, "out": 0}
        return usage

    # -- primitives -----------------------------------------------------

    def observe(self, page: Page, instruction: str) -> ActionResult:
        """Candidate element for `instruction`; validated to exactly one match."""
        if default_backend() == "real":
            return self._observe_real(page, instruction)
        snap = PageManager(page).dom_snapshot()
        if not snap.ok:
            return snap
        try:
            data = self._complete(
                _OBSERVE_SYSTEM, self._user(instruction, snap.extra["aria"]), "observe", instruction
            )
            spec = locator_spec(data)
            selector, _ = resolve_locator(page, spec)
        except Exception as exc:  # noqa: BLE001 — boundary: nothing raw escapes
            return self._fail("observe", "ObserveError", exc)
        return ActionResult(
            ok=True, action="observe", value=json.dumps({"selector": selector, "spec": spec})
        )

    def _observe_real(self, page: Page, instruction: str) -> ActionResult:
        """Real SDK observe → first candidate → same exactly-one validation."""
        start = time.monotonic()
        try:
            actions = self._real_backend().observe(page.url, instruction)
            if not actions:
                raise _AdapterError("real observe returned no candidates")
            first = actions[0]
            spec = locator_spec({"css": first["selector"]})
            selector, _ = resolve_locator(page, spec)
        except Exception as exc:  # noqa: BLE001 — boundary: nothing raw escapes
            self._log("observe", instruction, _ms(start), False, Usage())
            return self._fail("observe", "ObserveError", exc)
        self._log("observe", instruction, _ms(start), True, self._take(), json.dumps(actions[:3]))
        return ActionResult(
            ok=True,
            action="observe",
            value=json.dumps({"selector": selector, "spec": spec}),
            extra={"backend": "real-stagehand", "description": first.get("description", "")},
        )

    def act(self, page: Page, instruction: str) -> ActionResult:
        """One LLM call decides click/fill + target; execution via ActionExecutor."""
        if default_backend() == "real":
            return self._act_real(page, instruction)
        snap = PageManager(page).dom_snapshot()
        if not snap.ok:
            return snap
        try:
            data = self._complete(
                _ACT_SYSTEM, self._user(instruction, snap.extra["aria"]), "act", instruction
            )
            action = data.get("action")
            if action not in ("click", "fill"):
                raise _AdapterError(f"unsupported action: {action!r}")
            selector, locator = resolve_locator(page, locator_spec(data["target"]))
            if action == "click":
                res = run("act", locator.click)
            else:
                res = run("act", lambda: locator.fill(str(data.get("value", ""))))
        except Exception as exc:  # noqa: BLE001 — boundary: nothing raw escapes
            return self._fail("act", "ActError", exc)
        return ActionResult(
            ok=res.ok,
            action="act",
            value=selector,
            error=res.error,
            error_type=res.error_type,
            duration_ms=res.duration_ms,
        )

    def _act_real(self, page: Page, instruction: str) -> ActionResult:
        """Real SDK act on our frontmost page; result converted, never raised."""
        start = time.monotonic()
        try:
            res = self._real_backend().act(page.url, instruction)
            if not res.get("success"):
                raise _AdapterError(f"real act reported failure: {res.get('detail', '')[:200]}")
        except Exception as exc:  # noqa: BLE001 — boundary: nothing raw escapes
            self._log("act", instruction, _ms(start), False, Usage())
            return self._fail("act", "ActError", exc)
        self._log("act", instruction, _ms(start), True, self._take(), json.dumps(res)[:500])
        return ActionResult(
            ok=True,
            action="act",
            value=instruction,
            extra={"backend": "real-stagehand"},
            duration_ms=_ms(start),
        )

    def extract(self, page: Page, instruction: str, schema: dict[str, Any]) -> ActionResult:
        """Structured data per `schema`; required keys validated before returning."""
        if default_backend() == "real":
            return self._extract_real(page, instruction, schema)
        snap = PageManager(page).dom_snapshot()
        if not snap.ok:
            return snap
        try:
            data = self._complete(
                _EXTRACT_SYSTEM,
                f"Instruction: {instruction}\nSchema: {json.dumps(schema)}\n"
                + self._user("", snap.extra["aria"]),
                "extract",
                instruction,
            )
            missing = [k for k in schema.get("required", []) if k not in data]
            if missing:
                raise _AdapterError(f"missing required keys: {missing}")
        except Exception as exc:  # noqa: BLE001 — boundary: nothing raw escapes
            return self._fail("extract", "ExtractError", exc)
        return ActionResult(ok=True, action="extract", value=json.dumps(data))

    def _extract_real(self, page: Page, instruction: str, schema: dict[str, Any]) -> ActionResult:
        """Real SDK extract → required-keys check → same value shape as snapshot path."""
        start = time.monotonic()
        try:
            data = self._real_backend().extract(page.url, instruction, schema)
            if not isinstance(data, dict):
                raise _AdapterError(f"real extract returned non-object: {str(data)[:200]!r}")
            missing = [k for k in schema.get("required", []) if k not in data]
            if missing:
                raise _AdapterError(f"missing required keys: {missing}")
        except Exception as exc:  # noqa: BLE001 — boundary: nothing raw escapes
            self._log("extract", instruction, _ms(start), False, Usage())
            return self._fail("extract", "ExtractError", exc)
        self._log("extract", instruction, _ms(start), True, self._take(), json.dumps(data)[:500])
        return ActionResult(
            ok=True,
            action="extract",
            value=json.dumps(data),
            extra={"backend": "real-stagehand"},
        )

    # -- internals ------------------------------------------------------

    def ask(self, system: str, user: str, *, method: str = "ask", instruction: str = "") -> str:
        """Raw-text model call for non-primitive consumers (planner). Logged + counted."""
        start = time.monotonic()

        def _done(ok: bool, usage: Usage, response: str = "") -> None:
            latency_ms = int((time.monotonic() - start) * 1000)
            self._log(method, instruction or user[:200], latency_ms, ok, usage, response)

        try:
            text, usage = self._call(system, user)
        except _AdapterError:
            _done(False, Usage())
            raise
        _done(True, usage, text)
        return text

    def _call(self, system: str, user: str) -> tuple[str, Usage]:
        """One portal round-trip. Raises _AdapterError; bumps calls_made."""
        provider_cfg = self._config.to_provider_config()
        if provider_cfg is None:
            raise _AdapterError(f"no API key for provider={self._config.provider}")
        provider = OpenAICompatibleProvider(provider_cfg)
        self.calls_made += 1
        try:
            return self._portal.call(self._collect, provider, system, user)
        except _AdapterError:
            raise
        except Exception as exc:  # noqa: BLE001 — boundary: convert
            raise _AdapterError(f"{type(exc).__name__}: {str(exc)[:300]}") from exc

    def _complete(self, system: str, user: str, method: str, instruction: str) -> dict[str, Any]:
        """One blocking model call; logs everything; raises _AdapterError on failure."""
        start = time.monotonic()

        def _done(ok: bool, usage: Usage, response: str = "") -> None:
            latency_ms = int((time.monotonic() - start) * 1000)
            self._log(method, instruction, latency_ms, ok, usage, response)

        try:
            text, usage = self._call(system, user)
        except _AdapterError:
            _done(False, Usage())
            raise
        try:
            data = self._parse_json(text)
        except _AdapterError:
            _done(False, usage, text)
            raise
        _done(True, usage, text)
        return data

    async def _collect(
        self, provider: OpenAICompatibleProvider, system: str, user: str
    ) -> tuple[str, Usage]:
        try:
            async for event in provider.stream_response(
                model=self._config.model,
                system=system,
                messages=[UserMessage(content=user)],
                tools=[],
                session_id=self._session_id,
            ):
                if isinstance(event, AssistantDoneEvent):
                    return event.message.text, event.message.usage
                if isinstance(event, AssistantErrorEvent):
                    raise _AdapterError(event.error.text or "provider error")
            raise _AdapterError("empty provider stream")
        finally:
            await provider.aclose()

    def _log(
        self,
        method: str,
        instruction: str,
        latency_ms: int,
        ok: bool,
        usage: Usage,
        response: str = "",
    ) -> None:
        record = {
            "ts": datetime.now(UTC).isoformat(),
            "method": method,
            "instruction": instruction,
            "model": self._config.model,
            "provider": self._config.provider,
            "latency_ms": latency_ms,
            "ok": ok,
            "input_tokens": usage.input,
            "output_tokens": usage.output,
            "cost_usd": None,  # OpenCode Go publishes no per-model price
            "response": response[:500],
        }
        with LOG_PATH.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(record) + "\n")

    def _user(self, instruction: str, aria: str) -> str:
        head = f"Instruction: {instruction}\n" if instruction else ""
        return f"{head}Accessibility tree:\n{self._clip(aria)}"

    @staticmethod
    def _fail(action: str, error_type: str, exc: Exception) -> ActionResult:
        return ActionResult(ok=False, action=action, error=str(exc)[:500], error_type=error_type)

    @staticmethod
    def _clip(text: str) -> str:
        if len(text) <= _MAX_AX_CHARS:
            return text
        return text[:_MAX_AX_CHARS] + "\n…[truncated]"

    @staticmethod
    def _parse_json(text: str) -> dict[str, Any]:
        try:
            data = json.loads(text[text.index("{") : text.rindex("}") + 1])
        except ValueError as exc:
            raise _AdapterError(f"model did not return JSON: {text[:200]!r}") from exc
        if not isinstance(data, dict):
            raise _AdapterError(f"model returned non-object JSON: {text[:200]!r}")
        return data


class _AdapterError(Exception):
    """Internal control flow; converted to ActionResult at the primitive boundary."""
