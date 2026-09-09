"""Phase 2 live demo: all three primitives against a fixture.

observe → act → extract, with the call log printed at the end.
Backend: STAGEHAND_BACKEND=snapshot (default) or real (needs CDP browser, see below).
Usage:
  PYTHONPATH=src .venv/bin/python -m tau_agent.webhermes.stagehand.demo [--log PATH]
  STAGEHAND_BACKEND=real WEBHERMES_CDP_PORT=9222 PYTHONPATH=src .venv/bin/python -m ...
"""

from __future__ import annotations

import argparse
import json
import tempfile
import threading
from http.server import ThreadingHTTPServer
from pathlib import Path

from tau_agent.webhermes.browser.smoke import _Handler
from tau_agent.webhermes.stagehand import adapter as adapter_module
from tau_agent.webhermes.stagehand.adapter import StagehandAdapter, default_backend


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", default=None)
    args = ap.parse_args()
    adapter_module.LOG_PATH = Path(
        args.log or tempfile.mkdtemp(prefix="webhermes-llm-") + "/calls.jsonl"
    )

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()

    from tau_agent.webhermes.browser import ActionExecutor, BrowserManager, PageManager

    real = default_backend() == "real"
    mgr = BrowserManager(headless=True)
    mgr.start()
    sa = StagehandAdapter()
    try:
        ctx = mgr.new_session("demo")
        page = ctx.new_page()
        pm = PageManager(page)
        assert pm.goto(f"http://127.0.0.1:{server.server_port}/").ok

        obs = sa.observe(page, "the search input")
        print(f"observe: ok={obs.ok} value={obs.value} err={obs.error}")
        assert obs.ok, obs.error

        if real:
            # Real backend drives its own page: fill AND click through act.
            fill = sa.act(page, "fill the search input with python")
            print(f"act-fill: ok={fill.ok} err={fill.error}")
            assert fill.ok, fill.error
        else:
            assert ActionExecutor(page).fill("#q", "python").ok
        act = sa.act(page, "click the Search button")
        print(f"act: ok={act.ok} value={act.value} err={act.error}")
        assert act.ok, act.error

        schema = {
            "type": "object",
            "properties": {"result": {"type": "string"}},
            "required": ["result"],
        }
        ext = sa.extract(page, "the result text", schema)
        print(f"extract: ok={ext.ok} value={ext.value} err={ext.error}")
        assert ext.ok, ext.error
        assert json.loads(ext.value or "") == {"result": "results for: python"}
    finally:
        sa.close()
        mgr.stop()
        server.shutdown()

    print(f"--- call log ({adapter_module.LOG_PATH}) ---")
    print(adapter_module.LOG_PATH.read_text())
    print("ALL THREE PRIMITIVES PASS")


if __name__ == "__main__":
    main()
