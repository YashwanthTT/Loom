"""Phase 6 (MVP): markup drift → detect → recover → version up → green replay."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Page
from sqlmodel import select

import tau_agent.webhermes.components.base as base_module
from tau_agent.webhermes.browser import BrowserManager
from tau_agent.webhermes.components import Navigate
from tau_agent.webhermes.components.discovery import (
    UnknownComponentError,
    _save,
    discover_component,
    run_saved,
)
from tau_agent.webhermes.components.fixtures import serve, set_mutable
from tau_agent.webhermes.db import (
    Component,
    ComponentVersion,
    Failure,
    init_db,
    record_run,
    session,
)
from tau_agent.webhermes.healing import heal
from tau_agent.webhermes.stagehand.adapter import StagehandAdapter

VA_HTML = """<!doctype html><html><body><main>
<label for="a1">Search</label><input id="a1" name="q" />
</main></body></html>"""

VB_HTML = """<!doctype html><html><body><main><form>
<label for="b2">Find things</label><input id="b2" name="qq" placeholder="type here" />
</form></main></body></html>"""


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
def mutable_page(manager: BrowserManager, base_url: str) -> Iterator[Page]:
    set_mutable(VA_HTML)
    ctx = manager.new_session("heal")
    pg = ctx.new_page()
    assert Navigate().execute(pg, {"url": base_url + "mutable"}).ok
    yield pg
    ctx.close()


@pytest.fixture()
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "heal.db"
    monkeypatch.setenv("WEBHERMES_DB", str(path))
    init_db(path)
    monkeypatch.setattr(base_module, "ARTIFACT_DIR", tmp_path / "artifacts")
    return path


def test_heal_recovers_mutated_fixture(mutable_page: Page, base_url: str, db: Path) -> None:
    adapter = StagehandAdapter()
    try:
        comp = discover_component(
            mutable_page,
            name="dyn",
            description="the search box",
            action="fill",
            db_path=db,
            adapter=adapter,
        )
        assert comp.active_version == 1
        assert run_saved(mutable_page, "dyn", {"value": "x"}, db_path=db).result.ok

        set_mutable(VB_HTML)  # markup drift: ids renamed, label rewritten
        assert Navigate().execute(mutable_page, {"url": base_url + "mutable"}).ok
        assert not run_saved(mutable_page, "dyn", {"value": "x"}, db_path=db).result.ok

        calls_before = adapter.calls_made
        report = heal(
            mutable_page,
            "dyn",
            {"value": "healed"},
            db_path=db,
            adapter=adapter,
            retries=1,
            backoff_s=(0.1,),
        )
        assert report.healed and report.method == "recovered" and report.version == 2
        assert adapter.calls_made > calls_before and report.llm_calls >= 1

        assert run_saved(mutable_page, "dyn", {"value": "healed"}, db_path=db).result.ok
        assert mutable_page.input_value("#b2") == "healed"

        with session(db) as s:
            versions = s.exec(
                select(ComponentVersion).where(ComponentVersion.component_id == comp.id)
            ).all()
            assert sorted((v.version_number, v.is_active) for v in versions) == [
                (1, False),
                (2, True),
            ]
            row = s.get(Component, comp.id)
            assert row is not None and row.active_version == 2
            assert row.total_runs == 6 and row.failed_runs == 3
            assert row.success_rate == 0.5 and row.status == "degraded"
            fails = s.exec(select(Failure)).all()
            # Two failed executions recorded (detect run + heal retry); heal links its own.
            assert len(fails) == 2
            linked = [f for f in fails if f.resulting_version_id is not None]
            assert len(linked) == 1
            assert linked[0].recovery_attempted and "healed by v2" in linked[0].recovery_result
            assert linked[0].resulting_version_id == [v for v in versions if v.is_active][0].id
    finally:
        adapter.close()


def test_heal_healthy_component_spends_no_ai(mutable_page: Page, db: Path) -> None:
    adapter = StagehandAdapter()
    try:
        discover_component(
            mutable_page,
            name="dyn",
            description="the search box",
            action="fill",
            db_path=db,
            adapter=adapter,
        )
        before = adapter.calls_made
        report = heal(mutable_page, "dyn", {"value": "x"}, db_path=db, adapter=adapter)
        assert report.healed and report.method == "retry" and report.version == 1
        assert report.attempts == 1 and report.llm_calls == 0
        assert adapter.calls_made == before
        with session(db) as s:
            assert len(s.exec(select(ComponentVersion)).all()) == 1
    finally:
        adapter.close()


def test_heal_unknown_component_raises(db: Path) -> None:
    with pytest.raises(UnknownComponentError):
        heal(None, "nope", {}, db_path=db)  # type: ignore[arg-type]


def test_record_run_thresholds(tmp_path: Path) -> None:
    db = tmp_path / "stats.db"
    init_db(db)
    comp, _ = _save("s", "d", "click", "", {}, "#x", db)
    assert comp.id is not None
    assert record_run(db, comp.id, False) == (0.0, "broken")
    for _ in range(9):
        rate, status = record_run(db, comp.id, True)
    assert (rate, status) == (0.9, "healthy")
