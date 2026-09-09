"""Import-boundary check: `stagehand` must stay inside the stagehand/ seam package.

Architectural rule: Agent → Components → (Playwright | StagehandAdapter) → Browser.
Any violation is a build failure. The seam is the package (adapter.py + real.py),
so the real SDK can be swapped in without touching anything else.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "src" / "tau_agent" / "webhermes"
SEAM = ROOT / "stagehand"
_IMPORT_RE = re.compile(r"^\s*(import\s+stagehand\b|from\s+stagehand\b)", re.MULTILINE)


def test_stagehand_import_boundary() -> None:
    violations = []
    for path in sorted(ROOT.rglob("*.py")):
        if SEAM in path.parents or path.parent == SEAM:
            continue
        text = path.read_text(encoding="utf-8")
        if _IMPORT_RE.search(text):
            violations.append(str(path.relative_to(ROOT)))
    assert not violations, f"stagehand imported outside the stagehand/ seam: {violations}"
