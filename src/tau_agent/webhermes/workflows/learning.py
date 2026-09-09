"""Phase 10: successful ad-hoc runs become named workflows; repeats skip planning.

`run_task` is the planner entry point from here on: a similar saved workflow
(keyword overlap on the task text) executes directly with zero planning calls,
otherwise we plan once and persist the result as `created_by="learned"`.
"""

from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from playwright.sync_api import Page
from sqlmodel import select

from tau_agent.webhermes.components.registry import _tokens
from tau_agent.webhermes.db import Workflow, default_db, session
from tau_agent.webhermes.planner.planner import TaskReport, execute_task
from tau_agent.webhermes.workflows.engine import WorkflowReport, run_workflow, save_workflow


@dataclass(frozen=True, slots=True)
class LearnedReport:
    ok: bool
    reused_workflow: str | None  # name when a saved workflow ran, else None
    task_report: TaskReport | WorkflowReport | None = None
    llm_calls: int = 0
    detail: str = ""


def _similarity(a: str, b: str) -> float:
    ta, tb = _tokens(a), _tokens(b)
    if not ta or not tb:
        return 0.0
    return len(ta & tb) / min(len(ta), len(tb))


def find_workflow(
    task: str, *, domain: str = "", min_score: float = 0.5, db_path: Path | str | None = None
) -> Workflow | None:
    """Best learned/manual workflow match for `task`, or None."""
    db_path = db_path or default_db()
    with session(db_path) as s:
        rows = s.exec(select(Workflow)).all()
    best: Workflow | None = None
    best_score = 0.0
    for row in rows:
        sc = _similarity(task, f"{row.name} {row.description}")
        if sc > best_score:
            best, best_score = row, sc
    _ = domain  # workflows are domain-scoped via their components, not the row
    return best if best is not None and best_score >= min_score else None


def _slug(task: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", task.lower()).strip("_")[:40] or "task"


def _unique_name(slug: str, db_path: Path | str) -> str:
    with session(db_path) as s:
        names = {r.name for r in s.exec(select(Workflow)).all()}
    if slug not in names:
        return slug
    i = 2
    while f"{slug}-{i}" in names:
        i += 1
    return f"{slug}-{i}"


def run_task(
    page: Page,
    task: str,
    *,
    domain: str = "",
    context: dict[str, Any] | None = None,
    db_path: Path | str | None = None,
    adapter=None,
    ask_fn: Callable[[str, str], str] | None = None,
) -> LearnedReport:
    """Learned workflow if one matches; else plan, run, and persist on success."""
    db_path = db_path or default_db()
    match = find_workflow(task, domain=domain, db_path=db_path)
    if match is not None and match.name:
        wf = run_workflow(page, match.name, context=context, db_path=db_path, adapter=adapter)
        return LearnedReport(wf.ok, match.name, wf, wf.llm_calls, "reused saved workflow")
    rep = execute_task(
        page,
        task,
        domain=domain,
        context=context,
        db_path=db_path,
        adapter=adapter,
        ask_fn=ask_fn,
    )
    if rep.ok and rep.resolved_steps:
        name = _unique_name(_slug(task), db_path)
        save_workflow(
            name, rep.resolved_steps, description=task, created_by="learned", db_path=db_path
        )
        return LearnedReport(True, None, rep, rep.llm_calls, f"saved as workflow {name}")
    return LearnedReport(rep.ok, None, rep, rep.llm_calls, "planned, nothing to save")
