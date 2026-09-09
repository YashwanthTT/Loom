"""Phase 1 manual test: navigate → fill → click → read → screenshot → DOM → disk.

Serves a local fixture over HTTP (real browser, real HTTP, zero flakes, zero AI)
and repeats the full loop `--runs` times. Exit non-zero on any mismatch.
"""

from __future__ import annotations

import argparse
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from tau_agent.webhermes.browser import ActionExecutor, BrowserManager, PageManager

FIXTURE_HTML = """<!doctype html><html><body><main>
<h1>WebHermes smoke</h1>
<label for="q">Query</label><input id="q" name="q" />
<button id="go" type="button">Search</button>
<div id="result" role="status"></div>
</main><script>
document.getElementById('go').onclick = () => {
  document.getElementById('result').textContent =
    'results for: ' + document.getElementById('q').value;
};
</script></body></html>"""


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        body = FIXTURE_HTML.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        pass


def one_run(url: str, mgr: BrowserManager, outdir: Path, i: int) -> None:
    ctx = mgr.new_session(f"smoke-{i}", viewport={"width": 1280, "height": 800})
    try:
        pm = PageManager(ctx.new_page())
        ex = ActionExecutor(pm._page)
        steps = [
            ("goto", pm.goto(url)),
            ("fill", ex.fill("#q", "python")),
            ("click", ex.click("#go")),
            ("read", ex.read_text("#result")),
            ("shot-full", pm.screenshot(outdir / f"run{i}-full.png", full_page=True)),
            ("shot-el", pm.screenshot(outdir / f"run{i}-result.png", selector="#result")),
            ("dom", pm.dom_snapshot()),
        ]
        for name, res in steps:
            status = "ok" if res.ok else f"FAIL {res.error_type}: {res.error}"
            print(f"  run {i} {name}: {status} ({res.duration_ms}ms)")
            assert res.ok, f"run {i} step {name} failed: {res.error_type}: {res.error}"
        assert steps[3][1].value == "results for: python", f"wrong text: {steps[3][1].value}"
        assert "results for: python" in (steps[6][1].value or ""), "DOM missing result"
        aria = steps[6][1].extra.get("aria", "")
        assert '"results for: python"' in aria, "aria tree missing result"
        assert len(pm.requests) >= 1, "network log empty"
        print(f"  run {i}: PASS")
    finally:
        mgr.close_session(f"smoke-{i}")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", type=int, default=5)
    ap.add_argument("--headed", action="store_true")
    args = ap.parse_args()

    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    url = f"http://127.0.0.1:{server.server_port}/"
    outdir = Path(tempfile.mkdtemp(prefix="webhermes-smoke-"))
    print(f"fixture: {url}\nartifacts: {outdir}")

    mgr = BrowserManager(headless=not args.headed)
    mgr.start()
    try:
        for i in range(1, args.runs + 1):
            one_run(url, mgr, outdir, i)
    finally:
        mgr.stop()
        server.shutdown()
    print(f"ALL {args.runs} RUNS PASS — zero AI involvement")


if __name__ == "__main__":
    main()
