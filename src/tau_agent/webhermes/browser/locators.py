"""Deterministic locator resolution: specs → Playwright Locators.

Two accepted forms (both end up validated to exactly one live match):
- spec dicts: {"role","name"} > {"text"}/{"placeholder"} > {"css"} (semantic first).
- plain CSS strings (Phase 3 manual locators).

Lives in the browser layer (not the adapter) so components, discovery, and
replay all resolve identically without depending on AI code.
"""

from __future__ import annotations

import json
from typing import Any

from playwright.sync_api import Locator, Page


class LocatorSpecError(Exception):
    """A locator spec is malformed or doesn't resolve to exactly one element."""


def locator_spec(data: Any) -> dict[str, str]:
    """Normalize model output (or anything) into one canonical spec dict."""
    if isinstance(data, str):
        return {"css": data}  # ready-made selector; still validated below
    if not isinstance(data, dict):
        raise LocatorSpecError(f"bad locator spec: {data!r}")
    for keys in (("role", "name"), ("text",), ("placeholder",), ("css",)):
        if all(k in data for k in keys):
            return {k: str(data[k]) for k in keys}
    raise LocatorSpecError(f"bad locator spec: {data!r}")


def resolve_locator(page: Page, spec: dict[str, str]) -> tuple[str, Locator]:
    """Build the Locator for `spec`; raise unless it matches exactly one element."""
    if "role" in spec:
        locator = page.get_by_role(spec["role"], name=spec["name"])
        display = f"role={spec}"
    elif "text" in spec:
        locator = page.get_by_text(spec["text"])
        display = f"text={spec['text']!r}"
    elif "placeholder" in spec:
        locator = page.get_by_placeholder(spec["placeholder"])
        display = f"placeholder={spec['placeholder']!r}"
    else:
        locator = page.locator(spec["css"])
        display = f"css={spec['css']!r}"
    count = locator.count()
    if count != 1:
        raise LocatorSpecError(f"{display} matched {count} elements, want exactly 1")
    return display, locator


def resolve_stored(page: Page, stored: str) -> tuple[str, Locator]:
    """Resolve a Component.locator value (spec-JSON from discovery, or legacy CSS)."""
    try:
        spec = json.loads(stored)
    except ValueError:
        spec = stored
    if isinstance(spec, dict):
        return resolve_locator(page, locator_spec(spec))
    return resolve_locator(page, {"css": str(spec)})


def canonical(spec: dict[str, str]) -> str:
    """Storable form of a spec (what lands in Component/ComponentVersion.locator)."""
    return json.dumps(spec, sort_keys=True)
