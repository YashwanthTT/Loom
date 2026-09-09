"""Phase 6: retry the known locator first; only then spend AI on a new version.

History is preserved, never overwritten: recovery stages a new ComponentVersion,
activates it only after it executes + verifies, and links the Failure row that
caused it (the dashboard's recovery narrative reads straight off that link).
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from playwright.sync_api import Page
from sqlmodel import select

from tau_agent.webhermes.browser.locators import (
    LocatorSpecError,
    canonical,
    locator_spec,
    resolve_locator,
)
from tau_agent.webhermes.components.discovery import (
    _ACTION_CLASSES,
    DiscoveryError,
    UnknownComponentError,
    _save,
    activate_version,
)
from tau_agent.webhermes.db import Component, default_db, mark_recovered, record_run, session
from tau_agent.webhermes.stagehand.adapter import StagehandAdapter


@dataclass(frozen=True, slots=True)
class HealReport:
    healed: bool
    method: str  # "retry" | "recovered" | "failed"
    version: int  # active version afterwards
    attempts: int  # execute+verify rounds
    llm_calls: int
    failure_id: int | None
    detail: str = ""


def heal(
    page: Page,
    component_name: str,
    inputs: dict[str, Any],
    *,
    domain: str = "",
    db_path: Path | str | None = None,
    adapter: StagehandAdapter | None = None,
    retries: int = 2,
    backoff_s: tuple[float, ...] = (0.5, 1.0),
) -> HealReport:
    """Detect → retry with backoff → recover via observe → version up."""
    db_path = db_path or default_db()
    own_adapter = adapter is None
    adapter = adapter or StagehandAdapter()
    calls_before = adapter.calls_made
    try:
        with session(db_path) as s:
            row = s.exec(
                select(Component).where(
                    Component.name == component_name, Component.domain == domain
                )
            ).first()
            if row is None:
                raise UnknownComponentError(f"no component {component_name!r}")
            comp_id, description, action, schema, current, active_vn = (
                row.id,
                row.description,
                row.action_type,
                json.loads(row.input_schema or "{}"),
                row.locator,
                row.active_version,
            )
        try:
            cls = _ACTION_CLASSES[action]
        except KeyError as exc:
            raise DiscoveryError(f"stored action_type is unknown: {action!r}") from exc
        comp = cls(locator=current)

        failure_id: int | None = None
        attempts = 0
        for i in range(retries + 1):
            if i:
                time.sleep(backoff_s[min(i - 1, len(backoff_s) - 1)])
            result = comp.execute(page, inputs)
            verified = comp.verify(page, result).ok
            record_run(db_path, comp_id, result.ok and verified)
            attempts += 1
            if result.ok and verified:
                if failure_id is not None:
                    mark_recovered(db_path, failure_id, f"retry {i} succeeded")
                return HealReport(True, "retry", active_vn, attempts, 0, failure_id)
            if failure_id is None:
                failure_id = comp.last_failure_id
                comp._record_enabled = False  # one Failure row per heal, not per retry

        obs = adapter.observe(page, description or component_name)
        llm_calls = adapter.calls_made - calls_before
        if not obs.ok:
            mark_recovered(db_path, failure_id, f"observe failed: {obs.error}")
            return HealReport(
                False, "failed", active_vn, attempts, llm_calls, failure_id, obs.error or ""
            )
        try:
            spec = locator_spec(json.loads(obs.value or "")["spec"])
            resolve_locator(page, spec)  # live validation before staging anything
        except (LocatorSpecError, ValueError, KeyError, TypeError) as exc:
            mark_recovered(db_path, failure_id, f"new locator invalid: {exc}")
            return HealReport(False, "failed", active_vn, attempts, llm_calls, failure_id, str(exc))
        canon = canonical(spec)
        if canon == current:
            mark_recovered(db_path, failure_id, "locator unchanged; not locator drift")
            return HealReport(
                False, "failed", active_vn, attempts, llm_calls, failure_id, "locator unchanged"
            )

        _, staged_vn = _save(
            component_name, description, action, domain, schema, canon, db_path, make_active=False
        )
        trial = cls(locator=canon)
        trial._record_enabled = False  # candidate outcome lives in mark_recovered text
        result = trial.execute(page, inputs)
        verified = trial.verify(page, result).ok
        record_run(db_path, comp_id, result.ok and verified)
        attempts += 1
        if result.ok and verified:
            activated = activate_version(db_path, comp_id, staged_vn)
            mark_recovered(
                db_path, failure_id, f"healed by v{activated.version_number}", activated.id
            )
            return HealReport(
                True,
                "recovered",
                activated.version_number,
                attempts,
                llm_calls,
                failure_id,
                f"v{activated.version_number} {canon}",
            )
        mark_recovered(db_path, failure_id, f"candidate v{staged_vn} failed verification")
        return HealReport(
            False, "failed", active_vn, attempts, llm_calls, failure_id, "candidate failed"
        )
    finally:
        if own_adapter:
            adapter.close()
