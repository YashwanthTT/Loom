"""Phase 8: planner reuses registry, validates inputs, flags gaps — zero LLM spend."""

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
from tau_agent.webhermes.planner import PlanError, execute_task, plan_task


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
    ctx = manager.new_session("planner")
    pg = ctx.new_page()
    assert Navigate().execute(pg, {"url": base_url}).ok
    yield pg
    ctx.close()


@pytest.fixture()
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "plan.db"
    monkeypatch.setenv("WEBHERMES_DB", str(path))
    init_db(path)
    _save(
        "search",
        "search for a keyword",
        "search",
        "",
        {"required": ["query", "button"]},
        "#sq",
        path,
    )
    _save("location", "fill the location field", "fill", "", {"required": ["value"]}, "#q", path)
    _save("extract", "read page text", "extract", "", {}, "#blurb", path)
    return path


GOOD_PLAN = {
    "steps": [
        {
            "component": "search",
            "description": "search it",
            "action": "search",
            "input": {"query": "python", "button": "#search-btn"},
        },
        {
            "component": "location",
            "description": "set city",
            "action": "fill",
            "input": {"value": "Bangalore"},
        },
        {"component": "extract", "description": "read out", "action": "extract", "input": {}},
    ]
}


def test_plan_reuses_all_three(db: Path) -> None:
    plan, calls = plan_task(
        "find python jobs", db_path=db, ask_fn=lambda s, u: json.dumps(GOOD_PLAN)
    )
    assert calls == 1 and plan.reused == 3
    assert [st.component for st in plan.steps] == ["search", "location", "extract"]


def test_execute_task_runs_engine_with_zero_discovery(page: Page, db: Path) -> None:
    rep = execute_task(
        page, "find python jobs", db_path=db, ask_fn=lambda s, u: json.dumps(GOOD_PLAN)
    )
    assert rep.ok and rep.discovered == [] and rep.plan.reused == 3
    assert rep.llm_calls == 1 and rep.workflow is not None and rep.workflow.ok
    assert rep.workflow.deterministic and rep.workflow.llm_calls == 0


def test_missing_inputs_reprompt_once(db: Path) -> None:
    bad = {
        "steps": [
            {
                "component": "search",
                "description": "x",
                "action": "search",
                "input": {"query": "python"},
            }
        ]
    }
    answers = [json.dumps(bad), json.dumps(GOOD_PLAN)]
    plan, calls = plan_task("t", db_path=db, ask_fn=lambda s, u: answers.pop(0))
    assert calls == 2 and plan.reused == 3


def test_gap_flagged_for_discovery_not_invented(db: Path) -> None:
    gap = {
        "steps": [
            {
                "component": None,
                "description": "press the load more button",
                "action": "click",
                "input": {},
            }
        ]
    }
    plan, _ = plan_task("t", db_path=db, ask_fn=lambda s, u: json.dumps(gap))
    assert plan.reused == 0 and plan.steps[0].component is None
    assert plan.steps[0].action == "click"


def test_garbage_twice_raises(db: Path) -> None:
    with pytest.raises(PlanError):
        plan_task("t", db_path=db, ask_fn=lambda s, u: "hello there")
