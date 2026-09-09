"""SQLite via SQLModel. `init_db` once per path, then `session()` (auto-commit)."""

from __future__ import annotations

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel, create_engine

from tau_agent.webhermes.models import Component, ComponentVersion, Execution, Failure, Workflow

__all__ = [
    "DEFAULT_DB_PATH",
    "Component",
    "ComponentVersion",
    "Execution",
    "Failure",
    "Workflow",
    "init_db",
    "mark_recovered",
    "default_db",
    "record_run",
    "session",
]

DEFAULT_DB_PATH = Path(os.environ.get("WEBHERMES_DB", "webhermes.db"))


def default_db() -> Path:
    """Live read of WEBHERMES_DB (import-time DEFAULT_DB_PATH goes stale under setenv)."""
    return Path(os.environ.get("WEBHERMES_DB", "webhermes.db"))


_engines: dict[str, object] = {}


def _engine(db_path: Path | str):
    key = str(db_path)
    if key not in _engines:
        if key == ":memory:":
            eng = create_engine(
                "sqlite://", connect_args={"check_same_thread": False}, poolclass=StaticPool
            )
        else:
            eng = create_engine(f"sqlite:///{key}", connect_args={"check_same_thread": False})
        _engines[key] = eng
    return _engines[key]


def init_db(db_path: Path | str | None = None) -> None:
    SQLModel.metadata.create_all(_engine(db_path or default_db()))


@contextmanager
def session(db_path: Path | str | None = None) -> Iterator[Session]:
    """Yield a Session that commits on clean exit (objects stay usable: no expiry)."""
    s = Session(_engine(db_path or default_db()), expire_on_commit=False)
    try:
        yield s
        s.commit()
    except Exception:
        s.rollback()
        raise
    finally:
        s.close()


def record_run(db_path: Path | str, component_id: int, ok: bool) -> tuple[float, str]:
    """Fold one execution into success_rate/status. Returns (rate, status)."""
    with session(db_path) as s:
        comp = s.get(Component, component_id)
        if comp is None:
            raise LookupError(f"no component id={component_id}")
        comp.total_runs += 1
        if not ok:
            comp.failed_runs += 1
        rate = 1.0 - comp.failed_runs / comp.total_runs
        comp.success_rate = rate
        comp.status = "healthy" if rate >= 0.9 else "degraded" if rate >= 0.5 else "broken"
        return rate, comp.status


def mark_recovered(
    db_path: Path | str, failure_id: int | None, result: str, version_id: int | None = None
) -> None:
    """Link a Failure row to its recovery outcome (no-op when id is None/unknown)."""
    if failure_id is None:
        return
    with session(db_path) as s:
        row = s.get(Failure, failure_id)
        if row is None:
            return
        row.recovery_attempted = True
        row.recovery_result = result[:500]
        row.resulting_version_id = version_id
