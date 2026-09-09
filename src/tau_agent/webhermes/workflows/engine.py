"""Phase 7: deterministic multi-step workflows with critical flags and auto-heal.

Steps reference saved components by name; string inputs support {placeholders}
rendered from the initial context plus prior steps ({prev}, {step0}, ...).
"""

from __future__ import annotations

import json
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from playwright.sync_api import Page
from sqlmodel import select

from tau_agent.webhermes.components.discovery import UnknownComponentError, run_saved
from tau_agent.webhermes.db import Execution, Workflow, default_db, session
from tau_agent.webhermes.healing import recover as heal_module


@dataclass(frozen=True, slots=True)
class WorkflowReport:
    ok: bool
    status: str  # completed | partial | failed
    steps: list[dict[str, Any]] = field(default_factory=list)
    llm_calls: int = 0
    deterministic: bool = True
    execution_id: int | None = None


def save_workflow(
    name: str,
    steps: list[dict[str, Any]],
    *,
    description: str = "",
    created_by: str = "manual",
    db_path: Path | str | None = None,
) -> Workflow:
    """Persist a step sequence ([{component, input, critical?}]) as a Workflow row."""
    db_path = db_path or default_db()
    for i, step in enumerate(steps):
        if "component" not in step or "input" not in step:
            raise ValueError(f"step {i} needs 'component' and 'input': {step!r}")
    with session(db_path) as s:
        row = Workflow(
            name=name, description=description, steps=json.dumps(steps), created_by=created_by
        )
        s.add(row)
        s.flush()
        return row


def run_workflow(
    page: Page,
    name: str,
    *,
    context: dict[str, Any] | None = None,
    db_path: Path | str | None = None,
    adapter=None,
) -> WorkflowReport:
    """Run a saved workflow. Verification failures auto-trigger healing."""
    from tau_agent.webhermes.stagehand.adapter import StagehandAdapter

    db_path = db_path or default_db()
    own_adapter = adapter is None
    adapter = adapter or StagehandAdapter()
    try:
        with session(db_path) as s:
            wf = s.exec(select(Workflow).where(Workflow.name == name)).first()
            if wf is None:
                raise UnknownComponentError(f"no workflow {name!r}")
            steps = json.loads(wf.steps or "[]")
            workflow_id = wf.id
        return run_steps(
            page, steps, context=context, db_path=db_path, adapter=adapter, workflow_id=workflow_id
        )
    finally:
        if own_adapter:
            adapter.close()


def run_steps(
    page: Page,
    steps: list[dict[str, Any]],
    *,
    context: dict[str, Any] | None = None,
    db_path: Path | str | None = None,
    adapter=None,
    workflow_id: int | None = None,
) -> WorkflowReport:
    """Run an ad-hoc step list with the same semantics (used by the planner)."""
    from tau_agent.webhermes.stagehand.adapter import StagehandAdapter

    db_path = db_path or default_db()
    own_adapter = adapter is None
    adapter = adapter or StagehandAdapter()
    calls_before = adapter.calls_made
    try:
        with session(db_path) as s:
            exec_row = Execution(workflow_id=workflow_id, status="running", deterministic=True)
            s.add(exec_row)
            s.flush()
            execution_id = exec_row.id
        ctx: dict[str, Any] = dict(context or {})
        log: list[dict[str, Any]] = []
        failed_critical = False
        for i, step in enumerate(steps):
            entry = _run_step(page, step, ctx, db_path, adapter)
            log.append(entry)
            if entry["ok"]:
                ctx[f"step{i}"] = entry.get("value") or ""
                ctx["prev"] = entry.get("value") or ""
            elif step.get("critical", True):
                failed_critical = True
                break
        llm_calls = adapter.calls_made - calls_before
        if failed_critical:
            status = "failed"
        elif any(not e["ok"] for e in log):
            status = "partial"
        else:
            status = "completed"
        with session(db_path) as s:
            row = s.get(Execution, execution_id)
            if row is not None:
                row.status = status
                row.finished_at = datetime.now(UTC)
                row.steps_log = json.dumps(log)
                row.llm_calls_count = llm_calls
                row.deterministic = llm_calls == 0
        return WorkflowReport(
            ok=status != "failed",
            status=status,
            steps=log,
            llm_calls=llm_calls,
            deterministic=llm_calls == 0,
            execution_id=execution_id,
        )
    finally:
        if own_adapter:
            adapter.close()


def _run_step(
    page: Page, step: dict[str, Any], ctx: dict[str, Any], db_path: Path | str, adapter
) -> dict[str, Any]:
    name = step["component"]
    rendered = _render(step.get("input", {}), ctx)
    try:
        rep = run_saved(page, name, rendered, domain=step.get("domain", ""), db_path=db_path)
    except UnknownComponentError as exc:
        return {"component": name, "ok": False, "method": "missing", "detail": str(exc)}
    if rep.result.ok and rep.verified:
        return {
            "component": name,
            "ok": True,
            "method": "direct",
            "value": rep.result.value,
            "duration_ms": rep.result.duration_ms,
        }
    report = heal_module.heal(
        page, name, rendered, domain=step.get("domain", ""), db_path=db_path, adapter=adapter
    )
    return {
        "component": name,
        "ok": report.healed,
        "method": f"healed-{report.method}",
        "detail": report.detail,
        "version": report.version,
    }


def _render(inputs: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    """Fill {placeholders} from context; unknown keys pass through untouched."""

    class _Safe(defaultdict):
        def __missing__(self, key: str) -> str:
            return "{" + key + "}"

    safe = _Safe(str, ctx)
    out = {}
    for k, v in inputs.items():
        try:
            out[k] = v.format_map(safe) if isinstance(v, str) else v
        except (ValueError, AttributeError):
            out[k] = v
    return out
