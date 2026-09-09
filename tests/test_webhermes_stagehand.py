"""Phases 2+4: locator helpers live in the browser layer (no browser/key/spend)."""

from __future__ import annotations

import pytest

from tau_agent.webhermes.browser.locators import LocatorSpecError, locator_spec, resolve_locator
from tau_agent.webhermes.stagehand.adapter import StagehandAdapter, _AdapterError


def test_parse_json_strips_fences() -> None:
    out = StagehandAdapter._parse_json('```json\n{"role": "button", "name": "Go"}\n```')
    assert out == {"role": "button", "name": "Go"}


def test_parse_json_rejects_garbage() -> None:
    with pytest.raises(_AdapterError):
        StagehandAdapter._parse_json("no json here")


def test_locator_spec_priority() -> None:
    full = {"role": "textbox", "name": "Query", "text": "Query", "css": "#q"}
    assert locator_spec(full) == {"role": "textbox", "name": "Query"}
    assert locator_spec({"text": "Go", "css": "#go"}) == {"text": "Go"}
    assert locator_spec("#q") == {"css": "#q"}
    with pytest.raises(LocatorSpecError):
        locator_spec({"role": "button"})


def test_resolve_requires_exactly_one() -> None:
    class _Loc:
        def __init__(self, n: int) -> None:
            self._n = n

        def count(self) -> int:
            return self._n

    class _Page:
        def __init__(self, n: int) -> None:
            self._n = n

        def get_by_role(self, *a: object, **k: object) -> _Loc:
            return _Loc(self._n)

        def get_by_text(self, *a: object, **k: object) -> _Loc:
            return _Loc(self._n)

        def get_by_placeholder(self, *a: object, **k: object) -> _Loc:
            return _Loc(self._n)

        def locator(self, *a: object, **k: object) -> _Loc:
            return _Loc(self._n)

    selector, locator = resolve_locator(_Page(1), {"css": "#q"})
    assert selector == "css='#q'" and locator.count() == 1
    with pytest.raises(LocatorSpecError):
        resolve_locator(_Page(0), {"css": "#q"})
    with pytest.raises(LocatorSpecError):
        resolve_locator(_Page(3), {"css": "#q"})
