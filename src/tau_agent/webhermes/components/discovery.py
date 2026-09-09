"""Phase 4: NL description → observe → validated locator → saved Component.

Replay (`run_saved`) takes no adapter at all — AI-free by construction, with an
explicit deterministic/llm_calls report on every execution.
"""

from __future__ import annotations

import json
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
from tau_agent.webhermes.browser.results import ActionResult
from tau_agent.webhermes.components.base import BrowserComponent
from tau_agent.webhermes.components.library import (
    Click,
    Download,
    Extract,
    Fill,
    Navigate,
    Search,
    Select,
    Wait,
)
from tau_agent.webhermes.components.registry import find_matching_component
from tau_agent.webhermes.db import Component, ComponentVersion, default_db, record_run, session
from tau_agent.webhermes.stagehand.adapter import StagehandAdapter

_ACTION_CLASSES: dict[str, type[BrowserComponent]] = {
    "navigate": Navigate,
    "click": Click,
    "fill": Fill,
    "search": Search,
    "select": Select,
    "extract": Extract,
    "wait": Wait,
    "download": Download,
}


class DiscoveryError(Exception):
    """Discovery failed after all attempts (see message for the last error)."""


class UnknownComponentError(LookupError):
    """No saved component matches (replay looks up; it never discovers)."""


def _reuse_name(
    description: str, domain: str, action: str, db_path: Path | str, requested: str
) -> str:
    """Near-duplicate guard: version the existing row instead of creating a twin."""
    match = find_matching_component(description, domain, action=action, db_path=db_path)
    return match.name if match is not None else requested


@dataclass(frozen=True, slots=True)
class ReplayReport:
    result: ActionResult
    verified: bool
    deterministic: bool = True
    llm_calls: int = 0
    version: int = 0


def discover_component(
    page: Page,
    *,
    name: str,
    description: str,
    action: str,
    domain: str = "",
    input_schema: dict[str, Any] | None = None,
    db_path: Path | str | None = None,
    adapter: StagehandAdapter | None = None,
    max_attempts: int = 3,
    reuse: bool = True,
) -> Component:
    """Observe → validate (exactly one live match) → save as a new active version."""
    if action not in _ACTION_CLASSES:
        raise DiscoveryError(f"unknown action: {action!r}")
    db_path = db_path or default_db()
    if reuse:
        name = _reuse_name(description, domain, action, db_path, name)
    own_adapter = adapter is None
    adapter = adapter or StagehandAdapter()
    try:
        last_error = "no attempts made"
        for _ in range(max_attempts):
            obs = adapter.observe(page, description)
            if not obs.ok:
                last_error = f"{obs.error_type}: {obs.error}"
                continue
            try:
                spec = locator_spec(json.loads(obs.value or "")["spec"])
                resolve_locator(page, spec)  # live validation: exactly one match
            except (LocatorSpecError, ValueError, KeyError, TypeError) as exc:
                last_error = f"{type(exc).__name__}: {exc}"
                continue
            comp, _ = _save(
                name, description, action, domain, input_schema or {}, canonical(spec), db_path
            )
            return comp
        raise DiscoveryError(f"{max_attempts} attempts failed; last error: {last_error}")
    finally:
        if own_adapter:
            adapter.close()


def _save(
    name: str,
    description: str,
    action: str,
    domain: str,
    input_schema: dict[str, Any],
    locator: str,
    db_path: Path | str,
    make_active: bool = True,
    created_by: str = "stagehand",
) -> tuple[Component, int]:
    """Persist a locator as a new version; return (component, version_number)."""
    with session(db_path) as s:
        comp = s.exec(
            select(Component).where(Component.name == name, Component.domain == domain)
        ).first()
        if comp is None:
            comp = Component(
                name=name,
                description=description,
                input_schema=json.dumps(input_schema),
                locator=locator if make_active else "",
                action_type=action,
                domain=domain,
            )
            if not make_active:
                comp.active_version = 0
            s.add(comp)
            s.flush()
            version_number = 1
        else:
            latest = s.exec(
                select(ComponentVersion)
                .where(ComponentVersion.component_id == comp.id)
                .order_by(ComponentVersion.version_number.desc())  # type: ignore[arg-type]
            ).first()
            version_number = (latest.version_number if latest else 0) + 1
            if make_active:
                for old in s.exec(
                    select(ComponentVersion).where(
                        ComponentVersion.component_id == comp.id, ComponentVersion.is_active
                    )
                ).all():
                    old.is_active = False
                comp.locator = locator
                comp.active_version = version_number
                comp.status = "healthy"
        s.add(
            ComponentVersion(
                component_id=comp.id,
                version_number=version_number,
                locator=locator,
                created_by=created_by,
                is_active=make_active,
            )
        )
        return comp, version_number


def activate_version(
    db_path: Path | str, component_id: int, version_number: int
) -> ComponentVersion:
    """Mark a staged version active after it executed + verified. Old versions stay."""
    with session(db_path) as s:
        comp = s.get(Component, component_id)
        if comp is None:
            raise LookupError(f"no component id={component_id}")
        target = s.exec(
            select(ComponentVersion).where(
                ComponentVersion.component_id == component_id,
                ComponentVersion.version_number == version_number,
            )
        ).first()
        if target is None:
            raise LookupError(f"no v{version_number} for component id={component_id}")
        for old in s.exec(
            select(ComponentVersion).where(
                ComponentVersion.component_id == component_id, ComponentVersion.is_active
            )
        ).all():
            old.is_active = False
        target.is_active = True
        comp.locator = target.locator
        comp.active_version = target.version_number
        comp.status = "healthy"
        return target


def run_saved(
    page: Page,
    name: str,
    inputs: dict[str, Any],
    *,
    domain: str = "",
    db_path: Path | str | None = None,
) -> ReplayReport:
    """Execute a saved component straight through Playwright. No adapter, no LLM."""
    db_path = db_path or default_db()
    with session(db_path) as s:
        row = s.exec(
            select(Component).where(Component.name == name, Component.domain == domain)
        ).first()
        if row is None:
            raise UnknownComponentError(f"no component {name!r} in domain {domain!r}")
        comp_id, locator, action_type, version = (
            row.id,
            row.locator,
            row.action_type,
            row.active_version,
        )
    try:
        cls = _ACTION_CLASSES[action_type]
    except KeyError as exc:
        raise UnknownComponentError(f"unknown action_type: {action_type!r}") from exc
    comp = cls(locator=locator)
    result = comp.execute(page, inputs)
    verified = comp.verify(page, result).ok
    record_run(db_path, comp_id, result.ok and verified)
    return ReplayReport(result=result, verified=verified, version=version)
