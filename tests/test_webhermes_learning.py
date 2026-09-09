"""Phase 10: run once, learn; reword, reuse with zero planning calls."""

from __future__ import annotations

import json
from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Page

from tau_agent.webhermes.browser import BrowserManager
from tau_agent.webhermes.components import Navigate
from tau_agent.webhermes.components.discovery import _save
from tau_agent.webhermes.components.fixtures import serve
from tau_agent.webhermes.db import init_db
from tau_agent.webhermes.workflows import find_workflow, run_task, save_workflow


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
    ctx = manager.new_session("learn")
    pg = ctx.new_page()
    assert Navigate().execute(pg, {"url": base_url}).ok
    yield pg
    ctx.close()


@pytest.fixture()
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "learn.db"
    monkeypatch.setenv("WEBHERMES_DB", str(path))
    init_db(path)
    _save("search", "search for a keyword", "search", "", {}, "#sq", path)
    _save("extract", "read page text", "extract", "", {}, "#sresult", path)
    return path


PLAN = {
    "steps": [
        {
            "component": "search",
            "description": "search it",
            "action": "search",
            "input": {"query": "python", "button": "#search-btn"},
        },
        {"component": "extract", "description": "read out", "action": "extract", "input": {}},
    ]
}


def test_learn_then_reuse_with_zero_planning(page: Page, db: Path) -> None:
    first = run_task(
        page,
        "search the fixture for python",
        db_path=db,
        ask_fn=lambda s, u: json.dumps(PLAN),
    )
    assert first.ok and first.reused_workflow is None
    assert "saved as workflow" in first.detail

    def _boom(system: str, user: str) -> str:
        raise AssertionError("planner must not be called on reuse")

    second = run_task(page, "search fixture for python please", db_path=db, ask_fn=_boom)
    assert second.ok and second.reused_workflow is not None
    assert second.llm_calls == 0
    assert second.task_report is not None and second.task_report.deterministic


def test_find_workflow_similarity(db: Path) -> None:
    save_workflow(
        "find_python_jobs",
        [{"component": "search", "input": {}}],
        description="find python jobs in bangalore",
        db_path=db,
    )
    assert find_workflow("find python internships bangalore", db_path=db) is not None
    assert find_workflow("download the quarterly report", db_path=db) is None
