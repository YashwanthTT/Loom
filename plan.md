# WebHermes Plan — done through Phase 12 (MVP + agent + dashboard + benchmarks)

Core philosophy: **AI only for exploration/recovery; Playwright for all deterministic execution.**
System gets cheaper + more reliable per run as one-time AI observations freeze into AI-free components.

## 0. Locked decisions

- **Layout: `src/` only.** Agent/tool code lives in `src/tau_agent/webhermes/`
  (browser, stagehand, components, workflows, planner, healing, config, db, models);
  UI lives in `src/tau_coding/webhermes/` (Typer TUI, Streamlit app, shared queries).
  Tests stay in existing `tests/` so current `pytest`/`ruff` config keeps working.
  Reuse `src/tau_ai` (provider/env — OpenCode Go already works) and `src/tau_agent`
  (harness/loop, provider-neutral core). No Svelte, no new top-level dirs.
- **UI: TUI + Streamlit, both in `tau_coding`.** Typer commands for the 5 dashboard
  pages (`uv run tau webhermes <page>`); `dashboard_app.py` mirrors them in Streamlit.
  No FastAPI — nothing needed it.
- **LLM:** you hold only the OpenCode Go subscription (OpenAI-compatible,
  `OPENCODE_API_KEY` / `OPENCODE_MODEL` / base `https://opencode.ai/zen/go/v1`).
  Spec demands an OpenRouter/Ollama toggle, never hardcoded — implemented as one
  `LLM_PROVIDER=opencode|openrouter|ollama` env toggle over the existing
  `tau_ai.env.OpenAICompatibleConfig` (all three are OpenAI-compatible; only base_url/key/model differ).
  Default: `opencode`.
- **DB:** SQLModel tables (Component, ComponentVersion, Workflow, Execution, Failure)
  since Phase 4; `WEBHERMES_DB` env selects the file (live-read, tests isolate via setenv).

## 1. Non-negotiable architectural rule

```
Agent → Components → (Deterministic Playwright | StagehandAdapter) → Playwright → Browser
```

- `stagehand` importable **only** inside `src/tau_agent/webhermes/stagehand/`.
- Enforced by `tests/test_webhermes_boundaries.py` (stdlib `pathlib` grep, no shell script,
  runs under existing pytest config). Any violation = build failure, from Phase 0 on.
- **Real Stagehand works** (no Browserbase/model keys needed): `real.py` runs the actual
  SDK (`local_browser` + `observe`/`act`/`extract`) with inference routed to OpenCode Go
  through an LLM callback. `STAGEHAND_BACKEND=real` selects it; `snapshot` (default)
  keeps the zero-dependency path. Both log identical metrics.

## 2. Final layout (all phases complete)

```
src/tau_agent/webhermes/{browser,stagehand,components,workflows,planner,healing}/
src/tau_agent/webhermes/{config,db,models}.py
src/tau_coding/webhermes/{tui,queries,dashboard_app}.py   # `uv run tau webhermes <page>`
tests/test_webhermes_*.py  # import-boundary check + per-phase suites
```

Run the app: `uv run tau webhermes health|dashboard|components|workflows|executions|failures`
Web UI: `streamlit run src/tau_coding/webhermes/dashboard_app.py`

## 3. Build order (strict)

1. **Phases 1–5:** task → Stagehand exploration → component → Playwright locator → verification → saved component → replay
2. **Phase 6 (Self-Healing) = MVP BOUNDARY.** Rock-solid 1–6 before anything below.
3. Phase 7: Workflows. 9: Registry (before 8 — planner needs a registry to prefer). 8: Planner. 10: Learning.
4. Phase 11: TUI pages + Streamlit webUI (parallelizable once API surface stable, only after 1–6 validated).
5. Phase 12: Benchmarks (Run 1 cold N LLM calls/X sec vs Runs 2–4 near-zero, success maintained via healing).

**Do not build:** multi-agent, long-term autonomous planning, voice, mobile, complex memory,
distributed workers/K8s, custom browser, model-training pipelines.

## 4. Data model (Phase 3, SQLModel)

Component (locator, action_type, verification_strategy, fallback_strategy, active_version,
status healthy/degraded/broken, success_rate, domain) · ComponentVersion (created_by
stagehand/manual, is_active) · Workflow (ordered steps JSON [{component_id, input_template}],
created_by learned/manual) · Execution (status, steps_log JSON, llm_calls_count, deterministic bool) ·
Failure (error_type, screenshot_path, dom_snapshot_path, recovery_attempted/result,
resulting_version_id → ComponentVersion).

## 5. Phase exit criteria — all met ✅

- P0–P6 (MVP): health ok; boundary trips on violation; 5× browser loop; 3 primitives live;
  8 components green; discover→save→zero-LLM replay; broken locator → Failure row; drift → v2 → green.
- P7: `find_stuff` runs AI-free with input templating; heal/continue/stop semantics tested.
- P9: "something that searches for a keyword" → `search` across phrasings; dedup versions rows.
- P8: live task → 1 plan call → 2/2 reuse → extracted text; schema `default`s fill planner gaps.
- P10: run once (saved as learned workflow) → reworded rerun reuses with 0 planning calls.
- P11: `uv run tau webhermes <page>` reads real data; Streamlit mirrors it.
- P12: 2 tasks × 4 runs — 2 cold calls + 1 heal call, 0 replay calls, 100% success (numbers §6).

## 6. Measured benchmark (Phase 12, live fixture, 2026-09-09)

| task | run 1 (cold) | replays (avg) | replay LLM calls | success |
|---|---|---|---|---|
| fill_q | 2825ms/1 calls | 2473ms | 1 | 4/4 |
| click_go | 3606ms/1 calls | 38ms | 0 | 4/4 |
| **total** | 2 LLM calls | 1 LLM calls | | success 100% |

Run 3 broke both locators (fixture swap); healing spent 1 call on fill_q (click_go
re-resolved without AI — role+name survived the drift). Replay average for fill_q
includes the heal round (retries + observe); steady-state replays are ~40ms, ~0 calls.
