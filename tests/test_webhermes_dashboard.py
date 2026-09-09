"""Phase 11: dashboard reads real data; a non-technical observer can follow along."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from tau_agent.webhermes.components.discovery import _save
from tau_agent.webhermes.db import Execution, Failure, init_db, session
from tau_agent.webhermes.workflows import save_workflow
from tau_coding.webhermes import queries
from tau_coding.webhermes.tui import app as tui_app


@pytest.fixture()
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "dash.db"
    monkeypatch.setenv("WEBHERMES_DB", str(path))
    init_db(path)
    comp, _ = _save("search", "search it", "search", "jobs", {}, "#sq", path)
    assert comp.id is not None
    _save("search", "search it", "search", "jobs", {}, "#sq2", path)
    save_workflow(
        "find_jobs",
        [{"component": "search", "input": {"query": "x"}}],
        description="find jobs",
        created_by="learned",
        db_path=path,
    )
    with session(path) as s:
        s.add(
            Execution(
                workflow_id=1,
                status="completed",
                steps_log=json.dumps(
                    [{"component": "search", "ok": True, "method": "healed-recovered"}]
                ),
                llm_calls_count=1,
                deterministic=False,
            )
        )
        s.add(
            Failure(
                component_id=comp.id,
                error_type="VerificationFailed:exists",
                detail="locator drifted",
                screenshot_path="/tmp/s.png",
                dom_snapshot_path="/tmp/d.html",
                recovery_attempted=True,
                recovery_result="healed by v2",
                resulting_version_id=2,
            )
        )
    return path


def test_home_and_lists(db: Path) -> None:
    stats = queries.home_stats(db)
    assert stats == {
        "components": 1,
        "healthy": 1,
        "degraded": 0,
        "broken": 0,
        "executions": 1,
        "deterministic_runs": 0,
        "failures": 1,
        "recoveries": 1,
    }
    comps = queries.list_components(db)
    assert comps[0]["name"] == "search" and comps[0]["version"] == 2
    hist = queries.component_history("search", db)
    assert [(h["version"], h["active"]) for h in hist] == [(1, False), (2, True)]
    assert queries.component_history("nope", db) == []
    wfs = queries.list_workflows(db)
    assert wfs[0]["chain"] == "search" and wfs[0]["created_by"] == "learned"
    execs = queries.list_executions(db_path=db)
    assert execs[0]["status"] == "completed" and not execs[0]["deterministic"]
    fails = queries.list_failures(db_path=db)
    assert "recovered it → v2" in fails[0]["narrative"] and fails[0]["component"] == "search"


def test_tui_pages_render_seeded_data(db: Path) -> None:
    runner = CliRunner()
    out = runner.invoke(tui_app, ["dashboard"])
    assert out.exit_code == 0 and "components: 1" in out.output and "recovered" in out.output
    out = runner.invoke(tui_app, ["components"])
    assert "search v2 [healthy]" in out.output
    out = runner.invoke(tui_app, ["history", "search"])
    assert "* v2" in out.output and "v1" in out.output
    out = runner.invoke(tui_app, ["workflows"])
    assert "find_jobs [learned]: search" in out.output
    out = runner.invoke(tui_app, ["executions"])
    assert "completed ai-assisted (1 calls)" in out.output and "healed-recovered" in out.output
    out = runner.invoke(tui_app, ["failures"])
    assert "VerificationFailed:exists" in out.output and "recovered it → v2" in out.output


def test_tui_empty_db_reads_cleanly(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    from tau_agent.webhermes.db import init_db as _init

    empty = tmp_path / "empty.db"
    monkeypatch.setenv("WEBHERMES_DB", str(empty))
    _init(empty)
    runner = CliRunner()
    for cmd in (["dashboard"], ["components"], ["workflows"], ["executions"], ["failures"]):
        out = runner.invoke(tui_app, cmd)
        assert out.exit_code == 0, cmd


def test_streamlit_app_imports_without_running_server() -> None:
    import tau_coding.webhermes.dashboard_app as app

    assert callable(app.main)
