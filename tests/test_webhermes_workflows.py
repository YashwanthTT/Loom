"""Phase 7: workflows run end-to-end with zero LLM when locators hold."""

from __future__ import annotations

import json
import unittest.mock as mock
from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Page
from sqlmodel import select

import tau_agent.webhermes.workflows.engine as engine_module
from tau_agent.webhermes.browser import BrowserManager
from tau_agent.webhermes.components import Navigate
from tau_agent.webhermes.components.discovery import _save
from tau_agent.webhermes.components.fixtures import serve
from tau_agent.webhermes.db import Execution, init_db, session
from tau_agent.webhermes.healing import HealReport
from tau_agent.webhermes.workflows import run_workflow, save_workflow


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
    ctx = manager.new_session("workflow")
    pg = ctx.new_page()
    assert Navigate().execute(pg, {"url": base_url}).ok
    yield pg
    ctx.close()


@pytest.fixture()
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "wf.db"
    monkeypatch.setenv("WEBHERMES_DB", str(path))
    init_db(path)
    return path


def _seed(db: Path, base_url: str) -> None:
    _save("go_home", "open the fixture home", "navigate", "", {}, "", db, created_by="manual")
    _save("do_search", "search the fixture", "search", "", {}, "#sq", db, created_by="manual")
    _save("read_out", "read the results", "extract", "", {}, "#sresult", db, created_by="manual")
    save_workflow(
        "find_stuff",
        [
            {"component": "go_home", "input": {"url": base_url}},
            {"component": "do_search", "input": {"query": "{query}", "button": "#search-btn"}},
            {"component": "read_out", "input": {}},
        ],
        db_path=db,
    )


def test_workflow_runs_ai_free_with_templating(page: Page, base_url: str, db: Path) -> None:
    _seed(db, base_url)
    rep = run_workflow(page, "find_stuff", context={"query": "python"}, db_path=db)
    assert rep.ok and rep.status == "completed"
    assert rep.deterministic and rep.llm_calls == 0
    assert [s["method"] for s in rep.steps] == ["direct"] * 3
    assert rep.steps[2]["value"] == "results for: python"
    with session(db) as s:
        rows = s.exec(select(Execution)).all()
        assert len(rows) == 1
        row = rows[0]
        assert row.status == "completed" and row.deterministic and row.llm_calls_count == 0
        assert len(json.loads(row.steps_log)) == 3


def test_healed_step_continues_and_logs_recovery(
    page: Page, base_url: str, db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _save("broken_click", "click nothing", "click", "", {}, "#nope", db, created_by="manual")
    save_workflow(
        "with_heal",
        [
            {"component": "broken_click", "input": {}},
            {"component": "read_out", "input": {}},
        ],
        db_path=db,
    )
    _save("read_out", "read", "extract", "", {}, "#blurb", db, created_by="manual")
    fake = HealReport(True, "recovered", 2, 1, 0, None, "fake heal")
    monkeypatch.setattr(engine_module.heal_module, "heal", lambda *a, **k: fake)
    rep = run_workflow(page, "with_heal", db_path=db)
    assert rep.ok and rep.status == "completed" and rep.deterministic
    assert rep.steps[0]["method"] == "healed-recovered"


def test_critical_failure_stops_early(
    page: Page, base_url: str, db: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _save("broken_click", "click nothing", "click", "", {}, "#nope", db, created_by="manual")
    _save("read_out", "read", "extract", "", {}, "#blurb", db, created_by="manual")
    save_workflow(
        "critical_break",
        [
            {"component": "broken_click", "input": {}},
            {"component": "read_out", "input": {}},
        ],
        db_path=db,
    )
    fake = HealReport(False, "failed", 1, 3, 0, 7, "still broken")
    monkeypatch.setattr(engine_module.heal_module, "heal", lambda *a, **k: fake)
    rep = run_workflow(page, "critical_break", db_path=db)
    assert not rep.ok and rep.status == "failed"
    assert len(rep.steps) == 1  # stopped before step 2


def test_noncritical_failure_continues(page: Page, db: Path) -> None:
    _save("broken_click", "click nothing", "click", "", {}, "#nope", db, created_by="manual")
    _save("read_out", "read", "extract", "", {}, "#blurb", db, created_by="manual")
    save_workflow(
        "lenient",
        [
            {"component": "broken_click", "input": {}, "critical": False},
            {"component": "read_out", "input": {}},
        ],
        db_path=db,
    )
    with mock.patch.object(
        engine_module.heal_module,
        "heal",
        return_value=HealReport(False, "failed", 1, 1, 0, None, "nope"),
    ):
        rep = run_workflow(page, "lenient", db_path=db)
    assert rep.ok and rep.status == "partial" and len(rep.steps) == 2
