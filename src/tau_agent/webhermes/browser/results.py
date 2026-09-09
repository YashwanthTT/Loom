"""Structured results: every browser action returns data, never raises."""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field


@dataclass(frozen=True, slots=True)
class ActionResult:
    """One attempted browser action. `extra` carries forward-compatible detail
    (Phase 5 verification will put expected/actual here — no signature churn)."""

    ok: bool
    action: str
    value: str | None = None
    error: str | None = None
    error_type: str | None = None
    duration_ms: int = 0
    extra: dict[str, str] = field(default_factory=dict)


def run(action: str, fn: Callable[[], object]) -> ActionResult:
    """Execute `fn`, converting any exception into a failed ActionResult."""
    start = time.monotonic()
    try:
        raw = fn()
    except Exception as exc:  # noqa: BLE001 — the boundary: nothing raw escapes
        return ActionResult(
            ok=False,
            action=action,
            error=str(exc)[:500],
            error_type=type(exc).__name__,
            duration_ms=int((time.monotonic() - start) * 1000),
        )
    value = None if raw is None else (raw if isinstance(raw, str) else str(raw))
    return ActionResult(
        ok=True, action=action, value=value, duration_ms=int((time.monotonic() - start) * 1000)
    )
