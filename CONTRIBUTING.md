# Contributing to WebHermes

One rule governs everything: **AI is for exploration/recovery; Playwright executes.**

## Layering (enforced by `tests/test_webhermes_boundaries.py`)

```
Agent → Components → (Deterministic Playwright | StagehandAdapter) → Playwright → Browser
```

- `stagehand` may be imported **only** inside `src/tau_agent/webhermes/stagehand/`.
  Any other import fails the build — no exceptions, no re-exports.
  Two backends, one seam: `snapshot` (own prompts over our snapshots, default) and
  `real` (real SDK, own browser, our OpenCode model via LLM callback).
  Switch with `STAGEHAND_BACKEND=real`; the interface and metrics don't change.
- Components resolve `Locator`s via `browser/locators.py` and execute through `run()`,
  never touching the page directly. Failures return structured
  results (success/failure + detail), never raw exceptions.
- Recovery creates a **new** `ComponentVersion`; locators are never overwritten.
- Agent code lives in `src/tau_agent/webhermes/`; UI lives in `src/tau_coding/webhermes/`
  (`uv run tau webhermes <page>`). `tau_agent` core stays provider-neutral (enforced by
  `test_tau_agent_does_not_import_tau_ai`, which carves out only the webhermes subpackage).

## Process

All 12 phases are built (see `plan.md`). New work: add a test first, keep the boundary
green, show evidence.
