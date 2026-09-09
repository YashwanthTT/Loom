"""Phase 12: benchmark math is exact; cold-vs-replay shape asserted spend-free."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path
from types import SimpleNamespace

import pytest
from playwright.sync_api import Page

from tau_agent.webhermes.bench import BenchReport, RunMetrics, TaskBench, run_benchmark
from tau_agent.webhermes.browser import BrowserManager
from tau_agent.webhermes.components import Navigate
from tau_agent.webhermes.components.discovery import _save
from tau_agent.webhermes.components.fixtures import serve
from tau_agent.webhermes.db import init_db


@pytest.fixture(scope="module")
def base_url() -> Iterator[str]:
    server, url = serve()
    yield url
    server.shutdown()


@pytest.fixture(scope="module")
def manager() -> Iterator[BrowserManager]:
    mgr = BrowserManager(headless=True)
    mgr.start()
    yield mgr
    mgr.stop()


@pytest.fixture()
def page(manager: BrowserManager, base_url: str) -> Iterator[Page]:
    ctx = manager.new_session("bench")
    pg = ctx.new_page()
    assert Navigate().execute(pg, {"url": base_url}).ok
    yield pg
    ctx.close()


@pytest.fixture()
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "bench.db"
    monkeypatch.setenv("WEBHERMES_DB", str(path))
    init_db(path)
    _save("read_blurb", "read the blurb", "extract", "", {}, "#blurb", path)
    return path


def test_report_math() -> None:
    rep = BenchReport(
        [
            TaskBench(
                "a",
                [
                    RunMetrics(1, True, 4000, 2, "cold"),
                    RunMetrics(2, True, 50, 0, "replay"),
                    RunMetrics(3, True, 60, 0, "replay"),
                ],
            ),
            TaskBench(
                "b",
                [
                    RunMetrics(1, True, 3000, 1, "cold"),
                    RunMetrics(2, False, 40, 0, "replay"),
                    RunMetrics(3, True, 45, 0, "replay"),
                ],
            ),
        ]
    )
    assert rep.cold_llm == 3 and rep.replay_llm == 0
    assert rep.success_rate == pytest.approx(5 / 6)
    md = rep.markdown()
    assert "| a | 4000ms/2 calls | 55ms | 0 | 3/3 |" in md
    assert "success 83%" in md


def test_benchmark_shape_with_stubbed_discovery(
    page: Page, db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import tau_agent.webhermes.bench as bench_module

    fake_adapter = SimpleNamespace(calls_made=0)

    def _fake_discover(page, *, name, **kwargs):
        fake_adapter.calls_made += 1
        from tau_agent.webhermes.db import Component, session

        with session(db) as s:
            from sqlmodel import select

            return s.exec(select(Component).where(Component.name == name)).first()

    monkeypatch.setattr(bench_module, "discover_component", _fake_discover)
    rep = run_benchmark(
        page,
        [
            {
                "component": "read_blurb",
                "description": "read the blurb",
                "action": "extract",
                "inputs": {},
            }
        ],
        runs=3,
        db_path=db,
        adapter=fake_adapter,
    )
    assert rep.cold_llm == 1 and rep.replay_llm == 0 and rep.success_rate == 1.0
    assert [r.method for r in rep.tasks[0].runs] == ["cold", "replay", "replay"]
