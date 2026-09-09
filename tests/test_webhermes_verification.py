"""Phase 5: verification catches real failures; every failure persists with evidence."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Page
from sqlmodel import select

import tau_agent.webhermes.components.base as base_module
from tau_agent.webhermes.browser import BrowserManager
from tau_agent.webhermes.components import Click, Download, Extract, Fill, Navigate
from tau_agent.webhermes.components.fixtures import serve
from tau_agent.webhermes.components.verify import VerificationSpec
from tau_agent.webhermes.db import Failure, init_db, session


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
    ctx = manager.new_session("verify")
    pg = ctx.new_page()
    assert Navigate().execute(pg, {"url": base_url}).ok
    yield pg
    ctx.close()


@pytest.fixture()
def failure_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    db = tmp_path / "failures.db"
    monkeypatch.setenv("WEBHERMES_DB", str(db))
    init_db(db)
    monkeypatch.setattr(base_module, "ARTIFACT_DIR", tmp_path / "artifacts")
    return db


def _failures(db: Path) -> list:
    init_db(db)
    with session(db) as s:
        return list(s.exec(select(Failure)).all())


def test_fill_verifies_value_strict(page: Page, failure_db: Path) -> None:
    comp = Fill("#q")
    res = comp.execute(page, {"value": "hello"})
    assert res.ok
    vr = comp.verify(page, res)
    assert vr.ok and vr.confidence == "strict"
    assert _failures(failure_db) == []


def test_broken_locator_persists_evidence(page: Page, failure_db: Path) -> None:
    comp = Click("#missing")
    res = comp.execute(page, {})
    assert not res.ok  # structured failure, no raise
    vr = comp.verify(page, res)
    assert not vr.ok
    rows = _failures(failure_db)
    assert len(rows) == 1
    row = rows[0]
    assert row.error_type == "VerificationFailed:exists"
    assert "strategy=exists" in row.detail and "#missing" in row.detail
    assert Path(row.screenshot_path).is_file()
    assert Path(row.dom_snapshot_path).is_file()
    assert row.created_at is not None and not row.recovery_attempted


def test_strict_spec_failure_records_expected_vs_actual(page: Page, failure_db: Path) -> None:
    comp = Click("#go")
    res = comp.execute(page, {})
    assert res.ok
    comp.verification = VerificationSpec("text_appeared", {"expected": "never-present-xyz"})
    vr = comp.verify(page, res)
    assert not vr.ok and vr.confidence == "strict"
    rows = _failures(failure_db)
    assert len(rows) == 1 and "never-present-xyz" in rows[0].detail


def test_download_verifies_file_landed(page: Page, tmp_path: Path, failure_db: Path) -> None:
    dest = str(tmp_path / "hello.txt")
    comp = Download("#dl")
    res = comp.execute(page, {"save_as": dest})
    assert res.ok
    assert comp.verify(page, res).ok
    assert _failures(failure_db) == []


def test_navigate_verifies_url(page: Page, base_url: str, failure_db: Path) -> None:
    comp = Navigate()
    res = comp.execute(page, {"url": base_url + "second"})
    assert comp.verify(page, res).ok
    assert _failures(failure_db) == []


def test_extract_still_reads_after_verify_wiring(page: Page, failure_db: Path) -> None:
    comp = Extract("#blurb")
    res = comp.execute(page, {})
    assert res.value == "The quick brown fox." and comp.verify(page, res).ok
