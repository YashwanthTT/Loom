"""Phase 4: versioning + replay lookup need no browser and no LLM spend."""

from __future__ import annotations

import pytest
from sqlmodel import select

from tau_agent.webhermes.components.discovery import UnknownComponentError, _save, run_saved
from tau_agent.webhermes.db import ComponentVersion, init_db, session


def test_save_versions_and_deactivates(tmp_path) -> None:
    db = tmp_path / "v.db"
    init_db(db)
    first, first_vn = _save("search_box", "the search input", "fill", "", {}, '{"css": "#q"}', db)
    assert (first.active_version, first_vn) == (1, 1)
    second, second_vn = _save(
        "search_box", "the search input", "fill", "", {}, '{"css": "#q2"}', db
    )
    assert (second.active_version, second_vn) == (2, 2)
    assert second.locator == '{"css": "#q2"}'
    with session(db) as s:
        versions = s.exec(
            select(ComponentVersion).where(ComponentVersion.component_id == second.id)
        ).all()
        assert sorted((v.version_number, v.is_active) for v in versions) == [(1, False), (2, True)]


def test_save_staged_inactive_until_activated(tmp_path) -> None:
    from tau_agent.webhermes.components.discovery import activate_version

    db = tmp_path / "staged.db"
    init_db(db)
    comp, _ = _save("s", "d", "click", "", {}, '{"css": "#a"}', db)
    assert comp.id is not None
    staged, staged_vn = _save("s", "d", "click", "", {}, '{"css": "#b"}', db, make_active=False)
    assert (staged_vn, staged.active_version) == (2, 1)  # v2 exists but v1 still active
    activated = activate_version(db, comp.id, staged_vn)
    assert activated.version_number == 2 and activated.is_active


def test_run_saved_unknown_name_raises_before_touching_page(tmp_path) -> None:
    db = tmp_path / "empty.db"
    init_db(db)
    with pytest.raises(UnknownComponentError):
        run_saved(None, "nope", {}, db_path=db)  # type: ignore[arg-type]
