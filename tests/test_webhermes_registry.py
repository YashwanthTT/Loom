"""Phase 9: registry returns existing components across phrasings, no LLM."""

from __future__ import annotations

from pathlib import Path

import pytest

from tau_agent.webhermes.components.discovery import _reuse_name, _save
from tau_agent.webhermes.components.registry import find_matching_component
from tau_agent.webhermes.db import init_db


@pytest.fixture()
def db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    path = tmp_path / "reg.db"
    monkeypatch.setenv("WEBHERMES_DB", str(path))
    init_db(path)
    _save("search", "search for a keyword on the page", "search", "jobs", {}, "#sq", path)
    _save("location", "choose the city in the location field", "fill", "jobs", {}, "#loc", path)
    _save("extract", "read the job listings text", "extract", "jobs", {}, "#jobs", path)
    return path


def test_finds_search_across_phrasings(db: Path) -> None:
    for phrasing in (
        "something that searches for a keyword",
        "find the search box to look up a term",
        "query the page with a keyword",
    ):
        match = find_matching_component(phrasing, "jobs", db_path=db)
        assert match is not None and match.name == "search", phrasing


def test_action_filter_and_domain_scope(db: Path) -> None:
    assert find_matching_component("fill the location field", "jobs", db_path=db).name == "location"  # type: ignore[union-attr]
    assert find_matching_component("search for a keyword", "other", db_path=db) is None
    assert find_matching_component("search for a keyword", db_path=db) is not None
    assert (
        find_matching_component("search for a keyword", "jobs", action="fill", db_path=db) is None
    )


def test_no_match_below_threshold(db: Path) -> None:
    assert find_matching_component("download the quarterly invoice pdf", "jobs", db_path=db) is None


def test_save_versions_existing_row(db: Path) -> None:
    comp, vn = _save("search", "search for a keyword on the page", "search", "jobs", {}, "#sq", db)
    assert vn == 2 and comp.active_version == 2
    from sqlmodel import select

    from tau_agent.webhermes.db import Component, session

    with session(db) as s:
        rows = s.exec(select(Component).where(Component.name == "search")).all()
        assert len(rows) == 1


def test_reuse_guard_returns_existing_name(db: Path) -> None:
    assert _reuse_name("search for a keyword here", "jobs", "search", db, "brand_new") == "search"
    assert (
        _reuse_name("download the invoice pdf", "jobs", "download", db, "brand_new") == "brand_new"
    )
