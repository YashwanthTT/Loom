"""Phase 3: all 8 components pass on local fixtures with hardcoded locators, zero AI."""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

import pytest
from playwright.sync_api import Page

from tau_agent.webhermes.browser import BrowserManager
from tau_agent.webhermes.components import (
    Click,
    Download,
    Extract,
    Fill,
    Navigate,
    Search,
    Select,
    Wait,
)
from tau_agent.webhermes.components.fixtures import DOWNLOAD_BYTES, serve


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
    ctx = manager.new_session("components")
    pg = ctx.new_page()
    assert Navigate().execute(pg, {"url": base_url}).ok
    yield pg
    ctx.close()


def test_navigate(page: Page, base_url: str) -> None:
    res = Navigate().execute(page, {"url": base_url + "second"})
    assert res.ok and page.url.endswith("/second")


def test_click(page: Page) -> None:
    assert Click("#go").execute(page, {}).ok
    assert Extract("#clicked").execute(page, {}).value == "clicked"


def test_fill(page: Page) -> None:
    assert Fill("#q").execute(page, {"value": "hello"}).ok
    assert page.input_value("#q") == "hello"


def test_search(page: Page) -> None:
    assert Search("#sq").execute(page, {"query": "python", "button": "#search-btn"}).ok
    assert Extract("#sresult").execute(page, {}).value == "results for: python"


def test_select(page: Page) -> None:
    assert Select("#choice").execute(page, {"value": "b"}).ok
    assert page.input_value("#choice") == "b"


def test_extract(page: Page) -> None:
    res = Extract("#blurb").execute(page, {})
    assert res.ok and res.value == "The quick brown fox."


def test_wait(page: Page) -> None:
    res = Wait("#late").execute(page, {})
    assert res.ok and Extract("#late").execute(page, {}).value == "arrived"


def test_download(page: Page, tmp_path: Path) -> None:
    dest = str(tmp_path / "hello.txt")
    res = Download("#dl").execute(page, {"save_as": dest})
    assert res.ok and Path(dest).read_bytes() == DOWNLOAD_BYTES


def test_missing_inputs_are_structured_failures(page: Page) -> None:
    res = Fill("#q").execute(page, {})
    assert not res.ok and res.error_type == "InputError"
