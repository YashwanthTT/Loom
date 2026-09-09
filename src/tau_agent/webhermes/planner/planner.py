"""Phase 8: free-text task → component steps (reuse first, discover only gaps).

The LLM sees the registry and picks existing components; anything unmatched is
discovered once via Phase 4, then everything runs through the Phase 7 engine.
`ask_fn` is the LLM seam — tests inject canned JSON, production passes adapter.ask.
"""

from __future__ import annotations

import json
import re
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from playwright.sync_api import Page
from sqlmodel import select

from tau_agent.webhermes.components.discovery import _ACTION_CLASSES, discover_component
from tau_agent.webhermes.db import Component, default_db, session
from tau_agent.webhermes.workflows.engine import WorkflowReport, run_steps

_PLAN_SYSTEM = (
    "You turn a browser task into steps over known components. Reply with ONLY JSON, no fences: "
    '{"steps": [{"component": "<name or null>", "description": "<what the step does>", '
    '"action": "<click|fill|search|select|extract|wait|navigate|download>", "input": {...}}]}. '
    'RULES: prefer "component" names from the registry verbatim (copy "input"\'s required keys '
    'RULES: prefer "component" names from the registry verbatim (copy "input"\'s required keys '
    'exactly); use null ONLY when no component fits, with a concrete "description" and action. '
    'For input keys the task does not specify, copy the schema "default" when one is shown. '
    "Never invent component names."
)


class PlanError(Exception):
    """The plan is unusable (bad JSON, unknown action, schema mismatch after retry)."""


@dataclass(frozen=True, slots=True)
class PlannedStep:
    component: str | None
    description: str
    action: str
    input: dict[str, Any]


@dataclass(frozen=True, slots=True)
class Plan:
    steps: list[PlannedStep]
    reused: int = 0


@dataclass(frozen=True, slots=True)
class TaskReport:
    ok: bool
    plan: Plan
    discovered: list[str] = field(default_factory=list)
    workflow: WorkflowReport | None = None
    llm_calls: int = 0
    resolved_steps: list[dict[str, Any]] = field(default_factory=list)


def _registry_brief(domain: str, db_path: Path | str) -> tuple[str, dict[str, dict[str, Any]]]:
    with session(db_path) as s:
        rows = s.exec(select(Component)).all()
    usable = [r for r in rows if not domain or r.domain in ("", domain)]
    lines = [
        f"- {r.name} ({r.action_type}): {r.description} inputs={r.input_schema}" for r in usable
    ]
    schemas = {r.name: json.loads(r.input_schema or "{}") for r in usable}
    return "\n".join(lines) or "(empty — discover everything)", schemas


def plan_task(
    task: str,
    *,
    domain: str = "",
    db_path: Path | str | None = None,
    ask_fn: Callable[[str, str], str],
) -> tuple[Plan, int]:
    """Plan against the registry via `ask_fn`. Returns (plan, llm_calls); retries once."""
    db_path = db_path or default_db()
    brief, schemas = _registry_brief(domain, db_path)
    user = f"Task: {task}\nRegistry:\n{brief}"
    calls, feedback = 0, ""
    for _ in range(2):
        calls += 1
        try:
            raw = ask_fn(_PLAN_SYSTEM, user + feedback)
            return _validate(json.loads(_strip(raw)), schemas), calls
        except (ValueError, PlanError) as exc:
            feedback = f"\n\nPrevious plan invalid: {exc}. Fix and reply ONLY JSON."
    raise PlanError(f"unplannable after {calls} attempts: {feedback[:200]}")


def _strip(text: str) -> str:
    return text[text.index("{") : text.rindex("}") + 1]


def _validate(data: Any, schemas: dict[str, dict[str, Any]]) -> Plan:
    if not isinstance(data, dict) or not isinstance(data.get("steps"), list) or not data["steps"]:
        raise PlanError(f"plan needs a non-empty steps list: {str(data)[:200]!r}")
    steps, reused = [], 0
    for i, st in enumerate(data["steps"]):
        if not isinstance(st, dict):
            raise PlanError(f"step {i} is not an object")
        action = st.get("action")
        if action not in _ACTION_CLASSES:
            raise PlanError(f"step {i} has unknown action: {action!r}")
        comp = st.get("component")
        inputs = st.get("input", {})
        if not isinstance(inputs, dict):
            raise PlanError(f"step {i} input must be an object")
        if comp is not None:
            if comp not in schemas:
                raise PlanError(f"step {i} names unknown component: {comp!r}")
            missing = [k for k in schemas[comp].get("required", []) if k not in inputs]
            if missing:
                raise PlanError(f"step {i} ({comp}) missing inputs: {missing}")
            reused += 1
        steps.append(
            PlannedStep(comp, str(st.get("description", "") or comp or ""), action, inputs)
        )
    return Plan(steps, reused)


def execute_task(
    page: Page,
    task: str,
    *,
    domain: str = "",
    context: dict[str, Any] | None = None,
    db_path: Path | str | None = None,
    adapter=None,
    ask_fn: Callable[[str, str], str] | None = None,
) -> TaskReport:
    """Plan → discover gaps → run ad-hoc through the engine. One entry point."""
    from tau_agent.webhermes.stagehand.adapter import StagehandAdapter

    db_path = db_path or default_db()
    own_adapter = adapter is None
    adapter = adapter or StagehandAdapter()
    calls_before = adapter.calls_made
    try:
        ask = ask_fn or (lambda s, u: adapter.ask(s, u, method="plan", instruction=u[:200]))
        plan, plan_calls = plan_task(task, domain=domain, db_path=db_path, ask_fn=ask)
        steps, discovered = [], []
        for st in plan.steps:
            name = st.component
            if name is None:
                slug = re.sub(r"[^a-z0-9]+", "_", st.description.lower()).strip("_")[:40] or "step"
                comp = discover_component(
                    page,
                    name=slug,
                    description=st.description,
                    action=st.action,
                    domain=domain,
                    db_path=db_path,
                    adapter=adapter,
                )
                name, discovered = comp.name, discovered + [comp.name]
            steps.append({"component": name, "input": st.input})
        wf = run_steps(page, steps, context=context, db_path=db_path, adapter=adapter)
        shared = ask_fn is None  # plan calls already sit in the adapter delta then
        total = adapter.calls_made - calls_before + (0 if shared else plan_calls)
        return TaskReport(wf.ok, plan, discovered, wf, total, steps)
    finally:
        if own_adapter:
            adapter.close()
