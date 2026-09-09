"""Stagehand scaffold — the ONLY module allowed to import `stagehand`.

Three primitives (observe/act/extract) over URLs. Keyless calls fail soft
(ok=False) instead of raising, so chat + tools keep working offline.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from anyio.from_thread import start_blocking_portal

from loom_agent.tau_web.config import WebHermesConfig, load_config
from loom_agent.tau_web.stagehand.real import RealStagehand


@dataclass(slots=True)
class ActionResult:
    ok: bool
    action: str
    value: str = ""
    error: str = ""
    error_type: str = ""
    extra: dict[str, Any] = field(default_factory=dict)


class StagehandAdapter:
    """Thin URL-based facade over the real Stagehand SDK (own browser, our model)."""

    def __init__(self, config: WebHermesConfig | None = None, headless: bool = True) -> None:
        self._config = config or load_config()
        self._headless = headless
        self._portal_cm = start_blocking_portal()
        self._portal = self._portal_cm.__enter__()
        self._real: RealStagehand | None = None

    def close(self) -> None:
        if self._real is not None:
            self._real.close()
            self._real = None
        self._portal_cm.__exit__(None, None, None)

    def has_api_key(self) -> bool:
        """False when no key is configured — every LLM call would fail."""
        return self._config.to_provider_config() is not None

    def _backend(self) -> RealStagehand | None:
        if not self.has_api_key():
            return None
        if self._real is None:
            self._real = RealStagehand(
                self._portal, self._config, on_llm_call=None, headless=self._headless
            )
        return self._real

    def _no_key(self, action: str) -> ActionResult:
        return ActionResult(
            ok=False,
            action=action,
            error=f"no API key for provider={self._config.provider}",
            error_type="NoApiKey",
        )

    # -- primitives -----------------------------------------------------

    def observe(self, url: str, instruction: str) -> ActionResult:
        """Candidate elements for `instruction` on `url`."""
        backend = self._backend()
        if backend is None:
            return self._no_key("observe")
        try:
            actions = backend.observe(url, instruction)
        except Exception as exc:  # noqa: BLE001 — boundary: nothing raw escapes
            return ActionResult(ok=False, action="observe", error=str(exc)[:300], error_type="ObserveError")
        if not actions:
            return ActionResult(ok=False, action="observe", error="no candidates", error_type="ObserveError")
        first = actions[0]
        return ActionResult(
            ok=True, action="observe", value=first.get("selector", ""), extra={"backend": "stagehand"}
        )

    def act(self, url: str, instruction: str) -> ActionResult:
        """Perform `instruction` on `url` (navigate + act)."""
        backend = self._backend()
        if backend is None:
            return self._no_key("act")
        try:
            res = backend.act(url, instruction)
        except Exception as exc:  # noqa: BLE001 — boundary: nothing raw escapes
            return ActionResult(ok=False, action="act", error=str(exc)[:300], error_type="ActError")
        if not res.get("success"):
            return ActionResult(
                ok=False, action="act", error=str(res.get("detail", ""))[:300], error_type="ActError"
            )
        return ActionResult(ok=True, action="act", value=instruction, extra={"backend": "stagehand"})

    def extract(self, url: str, instruction: str, schema: dict[str, Any]) -> ActionResult:
        """Structured data per `schema` from `url`."""
        import json

        backend = self._backend()
        if backend is None:
            return self._no_key("extract")
        try:
            data = backend.extract(url, instruction, schema)
        except Exception as exc:  # noqa: BLE001 — boundary: nothing raw escapes
            return ActionResult(ok=False, action="extract", error=str(exc)[:300], error_type="ExtractError")
        return ActionResult(ok=True, action="extract", value=json.dumps(data), extra={"backend": "stagehand"})
