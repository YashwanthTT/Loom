"""Pluggable verification strategies. Each answers: did the action actually work?

Confidence is derived, not configured: exact/pattern/attribute/file checks are
"strict"; presence/absence/substring checks are "loose" (a loose failure is
weaker evidence than a strict one — Phase 6 uses this to avoid false healing).
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from playwright.sync_api import Page

from tau_agent.webhermes.browser.locators import resolve_stored


@dataclass(frozen=True, slots=True)
class VerificationSpec:
    """What to check. `strategy` + `params` ride on the component from Phase 3."""

    strategy: str = "none"
    params: dict[str, str] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class VerificationResult:
    ok: bool
    strategy: str = "none"
    detail: str = ""
    confidence: str = "loose"


_STRICT = {
    "url_exact",
    "url_pattern",
    "text_appeared",
    "count",
    "attribute",
    "input_value",
    "file_exists",
}


def check(
    strategy: str, page: Page, params: dict[str, str], inputs: dict[str, Any]
) -> VerificationResult:
    """Dispatch to the named strategy. Unknown names fail closed (never trusted)."""
    fn = _STRATEGIES.get(strategy)
    if fn is None:
        return VerificationResult(
            ok=False, strategy=strategy, detail=f"unknown strategy: {strategy}", confidence="strict"
        )
    confidence = "strict" if strategy in _STRICT else "loose"
    ok, detail = fn(page, params, inputs)
    return VerificationResult(ok=ok, strategy=strategy, detail=detail, confidence=confidence)


def _exists(page: Page, params: dict[str, str], inputs: dict[str, Any]) -> tuple[bool, str]:
    locator = resolve_stored(page, params["selector"])[1]
    n = locator.count()
    return n >= 1, f"expected >=1 match for {params['selector']!r}, found {n}"


def _disappeared(page: Page, params: dict[str, str], inputs: dict[str, Any]) -> tuple[bool, str]:
    locator = resolve_stored(page, params["selector"])[1]
    n = locator.count()
    return n == 0, f"expected 0 matches for {params['selector']!r}, found {n}"


def _url_exact(page: Page, params: dict[str, str], inputs: dict[str, Any]) -> tuple[bool, str]:
    return page.url == params["expected"], f"expected URL {params['expected']!r}, got {page.url!r}"


def _url_contains(page: Page, params: dict[str, str], inputs: dict[str, Any]) -> tuple[bool, str]:
    return params["expected"] in page.url, (
        f"expected URL containing {params['expected']!r}, got {page.url!r}"
    )


def _url_pattern(page: Page, params: dict[str, str], inputs: dict[str, Any]) -> tuple[bool, str]:
    matched = re.search(params["expected"], page.url) is not None
    return matched, f"expected URL matching {params['expected']!r}, got {page.url!r}"


def _text_appeared(page: Page, params: dict[str, str], inputs: dict[str, Any]) -> tuple[bool, str]:
    scope = params.get("selector", "body")
    if scope == "body":
        text = page.locator("body").inner_text()
    else:
        text = resolve_stored(page, scope)[1].inner_text()
    found = params["expected"] in text
    return found, f"expected text {params['expected']!r} in {scope!r} ({len(text)} chars)"


def _count(page: Page, params: dict[str, str], inputs: dict[str, Any]) -> tuple[bool, str]:
    n = resolve_stored(page, params["selector"])[1].count()
    return n == int(params["expected"]), f"expected {params['expected']} matches, found {n}"


def _attribute(page: Page, params: dict[str, str], inputs: dict[str, Any]) -> tuple[bool, str]:
    actual = resolve_stored(page, params["selector"])[1].get_attribute(params["attribute"])
    return actual == params["expected"], (
        f"expected {params['attribute']}={params['expected']!r}, got {actual!r}"
    )


def _input_value(page: Page, params: dict[str, str], inputs: dict[str, Any]) -> tuple[bool, str]:
    actual = resolve_stored(page, params["selector"])[1].input_value()
    return actual == params["expected"], f"expected value {params['expected']!r}, got {actual!r}"


def _file_exists(page: Page, params: dict[str, str], inputs: dict[str, Any]) -> tuple[bool, str]:
    p = Path(params["path"])
    ok = p.is_file()
    detail = (
        f"expected file at {params['path']!r}, got {p.stat().st_size} bytes"
        if ok
        else (f"expected file at {params['path']!r}, missing")
    )
    return ok, detail


_STRATEGIES = {
    "none": lambda page, params, inputs: (True, "no check configured"),
    "exists": _exists,
    "disappeared": _disappeared,
    "url_exact": _url_exact,
    "url_contains": _url_contains,
    "url_pattern": _url_pattern,
    "text_appeared": _text_appeared,
    "count": _count,
    "attribute": _attribute,
    "input_value": _input_value,
    "file_exists": _file_exists,
}
