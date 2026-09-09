"""Component ABC: the interface every phase builds on. Signatures are frozen here.

- execute(): real since Phase 3 (Locator-based, via the shared run() boundary).
- verify(): real since Phase 5 (strategies in verify.py; failures persist w/ evidence).
- recover(): stub until Phase 6 (retry + new ComponentVersion, never overwrite).
"""

from __future__ import annotations

import json
import os
from abc import ABC, abstractmethod
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import Locator, Page

from tau_agent.webhermes.browser.locators import resolve_stored
from tau_agent.webhermes.browser.page import PageManager
from tau_agent.webhermes.browser.results import ActionResult, run
from tau_agent.webhermes.components.verify import VerificationResult, VerificationSpec, check
from tau_agent.webhermes.db import Failure, default_db, init_db, session

ARTIFACT_DIR = Path(os.environ.get("WEBHERMES_ARTIFACTS", "webhermes-artifacts"))


class BrowserComponent(ABC):
    """One reusable browser capability. Locator is bound at construction (manual
    in Phase 3, Stagehand-discovered in Phase 4); only runtime values come via inputs."""

    name = "base"
    description = ""
    input_schema: dict[str, Any] = {}
    action = ""
    verification = VerificationSpec()
    fallback_strategy = "fail"
    version = 1
    _record_enabled = True  # heal() mutes retries; candidate outcomes live in mark_recovered

    def __init__(self, locator: str = "") -> None:
        self.locator = locator
        self._last: dict[str, Any] = {}
        self.last_failure_id: int | None = None

    @abstractmethod
    def execute(self, page: Page, inputs: dict[str, Any]) -> ActionResult:
        """Run the action deterministically. Never raises; never calls AI."""

    def verify(self, page: Page, result: ActionResult) -> VerificationResult:
        """Check the action worked; on failure persist evidence + Failure row."""
        self.last_failure_id = None
        if not result.ok:
            vr = VerificationResult(
                ok=False,
                strategy=self._spec(self._last).strategy,
                detail=f"action failed: {result.error_type}: {result.error}",
                confidence="strict",
            )
            if self._record_enabled:
                self.last_failure_id = self._record_failure(page, vr)
            return vr
        try:
            # An explicitly assigned instance spec wins over the input-derived one.
            spec = self.__dict__.get("verification", self._spec(self._last))
            vr = check(spec.strategy, page, spec.params, self._last)
        except Exception as exc:  # noqa: BLE001 — verify() never raises
            vr = VerificationResult(
                ok=False,
                strategy=self.verification.strategy,
                detail=f"checker crashed: {type(exc).__name__}: {str(exc)[:200]}",
                confidence="strict",
            )
        if not vr.ok and self._record_enabled:
            self.last_failure_id = self._record_failure(page, vr)
        return vr

    def recover(self, page: Page, inputs: dict[str, Any], failure: ActionResult) -> ActionResult:
        """Phase 6 implements Stagehand recovery + versioning."""
        del page, inputs, failure
        return ActionResult(
            ok=False,
            action="recover",
            error="not implemented (Phase 6)",
            error_type="NotImplemented",
        )

    def _spec(self, inputs: dict[str, Any]) -> VerificationSpec:
        """Expectations for this run; override when they depend on inputs."""
        del inputs
        return self.verification

    def _remember(self, inputs: dict[str, Any]) -> None:
        self._last = dict(inputs)

    def _target(self, page: Page) -> Locator:
        """Bound locator as a live Locator (spec-JSON or legacy CSS)."""
        return resolve_stored(page, self.locator)[1]

    def _act(self, action: str, page: Page, op) -> ActionResult:
        """Resolve the bound target, then run `op(target)` — never raises."""
        try:
            target = self._target(page)
        except Exception as exc:  # noqa: BLE001 — execute() never raises
            return ActionResult(
                ok=False, action=action, error=str(exc)[:500], error_type=type(exc).__name__
            )
        return run(action, lambda: op(target))

    def _record_failure(self, page: Page, vr: VerificationResult) -> int | None:
        """Screenshot + DOM snapshot + Failure row. Best-effort: never raises."""
        try:
            ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
            stamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%S%f")
            shot = ARTIFACT_DIR / f"{self.name}_{stamp}.png"
            dom_path = ARTIFACT_DIR / f"{self.name}_{stamp}.html"
            pm = PageManager(page)
            shot_ok = pm.screenshot(shot, full_page=True).ok
            shot_path = str(shot) if shot_ok else ""
            snap = pm.dom_snapshot()
            if snap.ok and snap.value:
                dom_path.write_text(snap.value, encoding="utf-8")
                dom_file = str(dom_path)
            else:
                dom_file = ""
            detail = (
                f"strategy={vr.strategy} confidence={vr.confidence} "
                f"inputs={json.dumps(self._last)[:500]} {vr.detail}"
            )
            init_db(default_db())
            with session(default_db()) as s:
                row = Failure(
                    error_type=f"VerificationFailed:{vr.strategy}",
                    detail=detail[:2000],
                    screenshot_path=shot_path,
                    dom_snapshot_path=dom_file,
                )
                s.add(row)
                s.flush()
                return row.id
        except Exception:
            return None

    def _checked(
        self, action: str, inputs: dict[str, Any], *required: str
    ) -> tuple[dict[str, Any] | None, ActionResult | None]:
        """Split validated values from an InputError result (5 lines callers don't repeat)."""
        self._remember(inputs)
        missing = [k for k in required if k not in inputs]
        if missing:
            return None, ActionResult(
                ok=False, action=action, error=f"missing inputs: {missing}", error_type="InputError"
            )
        return {k: inputs[k] for k in required}, None
