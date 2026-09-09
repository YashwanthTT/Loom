"""Phase 12: prove repeated execution gets cheaper and stays reliable.

Cold run discovers (LLM) then executes; replay runs execute AI-free.
Report shows the Run 1 → Runs 2..N drop in LLM calls and time.
"""

from __future__ import annotations

import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from playwright.sync_api import Page

from tau_agent.webhermes.components.discovery import discover_component, run_saved
from tau_agent.webhermes.db import default_db


@dataclass(frozen=True, slots=True)
class RunMetrics:
    run: int
    ok: bool
    duration_ms: int
    llm_calls: int
    method: str  # cold | replay | healed


@dataclass(frozen=True, slots=True)
class TaskBench:
    component: str
    runs: list[RunMetrics] = field(default_factory=list)

    @property
    def cold(self) -> RunMetrics:
        return self.runs[0]

    @property
    def replays(self) -> list[RunMetrics]:
        return self.runs[1:]

    @property
    def replay_llm(self) -> int:
        return sum(r.llm_calls for r in self.replays)

    @property
    def replay_ms(self) -> int:
        return sum(r.duration_ms for r in self.replays)


@dataclass(frozen=True, slots=True)
class BenchReport:
    tasks: list[TaskBench] = field(default_factory=list)

    @property
    def cold_llm(self) -> int:
        return sum(t.cold.llm_calls for t in self.tasks)

    @property
    def replay_llm(self) -> int:
        return sum(t.replay_llm for t in self.tasks)

    @property
    def success_rate(self) -> float:
        all_runs = [r for t in self.tasks for r in t.runs]
        return sum(1 for r in all_runs if r.ok) / len(all_runs) if all_runs else 0.0

    def markdown(self) -> str:
        lines = ["| task | run 1 (cold) | replays (avg) | replay LLM calls | success |"]
        lines.append("|---|---|---|---|---|")
        for t in self.tasks:
            n = len(t.replays) or 1
            lines.append(
                f"| {t.component} | {t.cold.duration_ms}ms/{t.cold.llm_calls} calls | "
                f"{t.replay_ms // n}ms | {t.replay_llm} | "
                f"{sum(r.ok for r in t.runs)}/{len(t.runs)} |"
            )
        lines.append(
            f"| **total** | {self.cold_llm} LLM calls | {self.replay_llm} LLM calls | "
            f"| success {self.success_rate:.0%} |"
        )
        return "\n".join(lines)


def run_benchmark(
    page: Page,
    tasks: list[dict[str, Any]],
    *,
    runs: int = 4,
    db_path: Path | str | None = None,
    adapter=None,
    mutate: Callable[[int], None] | None = None,
) -> BenchReport:
    """Benchmark tasks: cold discover+execute, then AI-free replays.

    `mutate(run_index)` optionally rewrites the fixture before a run to exercise
    healing (that run then logs method="healed" when recovery succeeds).
    """
    db_path = db_path or default_db()
    benches = []
    for spec in tasks:
        runs_out: list[RunMetrics] = []
        for i in range(1, runs + 1):
            if mutate is not None:
                mutate(i)
            start = time.monotonic()
            calls_before = adapter.calls_made if adapter is not None else 0
            if i == 1:
                comp = discover_component(
                    page,
                    name=spec["component"],
                    description=spec["description"],
                    action=spec["action"],
                    domain=spec.get("domain", ""),
                    db_path=db_path,
                    adapter=adapter,
                )
                rep = run_saved(page, comp.name, spec["inputs"], db_path=db_path)
                method = "cold"
            else:
                rep = run_saved(
                    page,
                    spec["component"],
                    spec["inputs"],
                    db_path=db_path,
                    domain=spec.get("domain", ""),
                )
                method = "replay"
                if not (rep.result.ok and rep.verified) and adapter is not None:
                    from tau_agent.webhermes.healing import heal

                    report = heal(
                        page,
                        spec["component"],
                        spec["inputs"],
                        domain=spec.get("domain", ""),
                        db_path=db_path,
                        adapter=adapter,
                    )
                    if report.healed:
                        method = "healed"
                        rep = run_saved(
                            page,
                            spec["component"],
                            spec["inputs"],
                            db_path=db_path,
                            domain=spec.get("domain", ""),
                        )
            llm = (adapter.calls_made - calls_before) if adapter is not None else 0
            runs_out.append(
                RunMetrics(
                    run=i,
                    ok=rep.result.ok and rep.verified,
                    duration_ms=int((time.monotonic() - start) * 1000),
                    llm_calls=llm,
                    method=method,
                )
            )
        benches.append(TaskBench(spec["component"], runs_out))
    return BenchReport(benches)
