"""All five WebHermes tables (spec data model). JSON columns are TEXT-encoded.

Only Component/ComponentVersion are used before Phase 7; the rest are defined
now because every later phase depends on this shape, not because they're wired.
"""

from __future__ import annotations

from datetime import UTC, datetime

from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(UTC)


class Component(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    description: str = ""
    input_schema: str = "{}"
    locator: str = ""
    action_type: str = ""
    verification_strategy: str = "none"
    fallback_strategy: str = "fail"
    active_version: int = 1
    status: str = "healthy"
    success_rate: float = 1.0
    total_runs: int = 0  # Phase 6 counters behind success_rate (Execution rows join in Phase 7)
    failed_runs: int = 0
    domain: str = Field(default="", index=True)
    created_at: datetime = Field(default_factory=_now)


class ComponentVersion(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    component_id: int = Field(foreign_key="component.id", index=True)
    version_number: int = 1
    locator: str = ""
    created_by: str = "stagehand"
    is_active: bool = True
    created_at: datetime = Field(default_factory=_now)


class Workflow(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(index=True)
    description: str = ""
    steps: str = "[]"
    created_by: str = "manual"
    created_at: datetime = Field(default_factory=_now)


class Execution(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    workflow_id: int | None = Field(default=None, foreign_key="workflow.id")
    component_id: int | None = Field(default=None, foreign_key="component.id")
    status: str = ""
    started_at: datetime = Field(default_factory=_now)
    finished_at: datetime | None = None
    steps_log: str = "[]"
    llm_calls_count: int = 0
    deterministic: bool = True


class Failure(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    execution_id: int | None = Field(default=None, foreign_key="execution.id")
    component_id: int | None = Field(default=None, foreign_key="component.id")
    error_type: str = ""
    detail: str = ""  # strategy + expected vs actual + inputs (Phase 5 requires these persisted)
    screenshot_path: str = ""
    dom_snapshot_path: str = ""
    recovery_attempted: bool = False
    recovery_result: str = ""
    resulting_version_id: int | None = Field(default=None, foreign_key="componentversion.id")
    created_at: datetime = Field(default_factory=_now)
