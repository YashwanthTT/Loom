"""Dashboard queries: plain-data reads shared by the TUI and the Streamlit app."""

from __future__ import annotations

import json
from pathlib import Path

from sqlmodel import select

from tau_agent.webhermes.db import (
    Component,
    ComponentVersion,
    Execution,
    Failure,
    Workflow,
    default_db,
    session,
)

Row = dict


def _db(db_path: Path | str | None) -> Path | str:
    return db_path or default_db()


def home_stats(db_path: Path | str | None = None) -> Row:
    """Counts a non-technical observer needs: components, health, runs, recoveries."""
    db_path = _db(db_path)
    with session(db_path) as s:
        comps = s.exec(select(Component)).all()
        execs = s.exec(select(Execution)).all()
        fails = s.exec(select(Failure)).all()
    healthy = sum(1 for c in comps if c.status == "healthy")
    return {
        "components": len(comps),
        "healthy": healthy,
        "degraded": sum(1 for c in comps if c.status == "degraded"),
        "broken": sum(1 for c in comps if c.status == "broken"),
        "executions": len(execs),
        "deterministic_runs": sum(1 for e in execs if e.deterministic),
        "failures": len(fails),
        "recoveries": sum(1 for f in fails if f.recovery_attempted and f.resulting_version_id),
    }


def list_components(db_path: Path | str | None = None) -> list[Row]:
    db_path = _db(db_path)
    with session(db_path) as s:
        rows = s.exec(select(Component).order_by(Component.name)).all()  # type: ignore[arg-type]
    return [
        {
            "name": c.name,
            "version": c.active_version,
            "status": c.status,
            "success_rate": round(c.success_rate, 2),
            "domain": c.domain or "-",
            "action": c.action_type,
        }
        for c in rows
    ]


def component_history(name: str, db_path: Path | str | None = None) -> list[Row]:
    db_path = _db(db_path)
    with session(db_path) as s:
        comp = s.exec(select(Component).where(Component.name == name)).first()
        if comp is None or comp.id is None:
            return []
        versions = s.exec(
            select(ComponentVersion)
            .where(ComponentVersion.component_id == comp.id)
            .order_by(ComponentVersion.version_number)  # type: ignore[arg-type]
        ).all()
    return [
        {
            "version": v.version_number,
            "locator": v.locator,
            "by": v.created_by,
            "active": v.is_active,
            "created": str(v.created_at),
        }
        for v in versions
    ]


def list_workflows(db_path: Path | str | None = None) -> list[Row]:
    """Each workflow with its step chain rendered as `a → b → c`."""
    db_path = _db(db_path)
    with session(db_path) as s:
        rows = s.exec(select(Workflow).order_by(Workflow.name)).all()  # type: ignore[arg-type]
    out = []
    for w in rows:
        try:
            chain = " → ".join(st.get("component", "?") for st in json.loads(w.steps or "[]"))
        except ValueError:
            chain = "?"
        out.append({"name": w.name, "chain": chain or "-", "created_by": w.created_by})
    return out


def list_executions(limit: int = 20, db_path: Path | str | None = None) -> list[Row]:
    db_path = _db(db_path)
    with session(db_path) as s:
        rows = s.exec(select(Execution).order_by(Execution.id.desc())).all()  # type: ignore[union-attr]
    out = []
    for e in rows[:limit]:
        try:
            steps = json.loads(e.steps_log or "[]")
        except ValueError:
            steps = []
        out.append(
            {
                "id": e.id,
                "status": e.status,
                "deterministic": e.deterministic,
                "llm_calls": e.llm_calls_count,
                "workflow_id": e.workflow_id,
                "steps": [
                    (st.get("component", "?"), st.get("method", "?"), st.get("ok")) for st in steps
                ],
            }
        )
    return out


def list_failures(limit: int = 20, db_path: Path | str | None = None) -> list[Row]:
    """Failures with the recovery narrative attached (what fixed it, which version)."""
    db_path = _db(db_path)
    with session(db_path) as s:
        fails = s.exec(select(Failure).order_by(Failure.id.desc())).all()  # type: ignore[union-attr]
        versions = {v.id: v for v in s.exec(select(ComponentVersion)).all()}
        comps = {c.id: c.name for c in s.exec(select(Component)).all()}
    out = []
    for f in fails[:limit]:
        v = versions.get(f.resulting_version_id or -1)
        narrative = "no recovery yet"
        if f.recovery_attempted and v is not None:
            narrative = f"recovered it → v{v.version_number} ({f.recovery_result})"
        elif f.recovery_attempted:
            narrative = f"recovery attempted: {f.recovery_result or 'no detail'}"
        out.append(
            {
                "id": f.id,
                "component": comps.get(f.component_id or -1, "-"),
                "error": f.error_type,
                "narrative": narrative,
                "screenshot": f.screenshot_path,
                "dom": f.dom_snapshot_path,
                "created": str(f.created_at),
            }
        )
    return out
