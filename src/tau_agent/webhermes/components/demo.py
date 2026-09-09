"""Phase 4 exit proof: discover "the search input" first pass, save, replay AI-free.

Replay takes no adapter — zero Stagehand calls is structural, and the demo
asserts the call log is byte-identical before/after replay.
Usage: PYTHONPATH=src .venv/bin/python -m webhermes.components.demo
"""

from __future__ import annotations

import tempfile
from pathlib import Path

from tau_agent.webhermes.browser import BrowserManager
from tau_agent.webhermes.components import Navigate
from tau_agent.webhermes.components.discovery import discover_component, run_saved
from tau_agent.webhermes.components.fixtures import serve
from tau_agent.webhermes.db import init_db
from tau_agent.webhermes.stagehand import adapter as adapter_module
from tau_agent.webhermes.stagehand.adapter import StagehandAdapter


def _log_size() -> int:
    p = adapter_module.LOG_PATH
    return p.stat().st_size if p.exists() else 0


def main() -> None:
    tmp = Path(tempfile.mkdtemp(prefix="webhermes-phase4-"))
    adapter_module.LOG_PATH = tmp / "calls.jsonl"
    db_path = tmp / "webhermes.db"
    init_db(db_path)

    server, url = serve()
    mgr = BrowserManager(headless=True)
    mgr.start()
    adapter = StagehandAdapter()
    try:
        ctx = mgr.new_session("discover")
        page = ctx.new_page()
        assert Navigate().execute(page, {"url": url}).ok

        comp = discover_component(
            page,
            name="search_box",
            description="the search input",
            action="fill",
            db_path=db_path,
            adapter=adapter,
        )
        print(f"discovered: {comp.name} v{comp.active_version} locator={comp.locator}")
        print(f"discovery LLM calls: {adapter.calls_made}")
        assert comp.active_version == 1 and adapter.calls_made >= 1

        before = _log_size()
        first = run_saved(page, "search_box", {"value": "python"}, db_path=db_path)
        second = run_saved(page, "search_box", {"value": "python"}, db_path=db_path)
        assert _log_size() == before, "replay made LLM calls"
        for rep in (first, second):
            assert rep.result.ok, rep.result.error
            assert rep.deterministic and rep.llm_calls == 0 and rep.verified
        assert page.input_value("#sq") == "python" or page.input_value("#q") == "python"
        print(
            f"replay x2: ok deterministic={first.deterministic} "
            f"llm_calls={first.llm_calls} version={first.version}"
        )
    finally:
        adapter.close()
        mgr.stop()
        server.shutdown()
    print("DISCOVER → SAVE → AI-FREE REPLAY: PASS")


if __name__ == "__main__":
    main()
