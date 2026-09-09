"""Local fixture server for component tests: two pages + a download, zero flakes."""

from __future__ import annotations

import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

HOME_HTML = """<!doctype html><html><body><main>
<h1>Components fixture</h1>
<a id="next" href="/second">Second page</a>
<button id="go" type="button">Go</button><div id="clicked" role="status"></div>
<label for="q">Query</label><input id="q" name="q" />
<label for="sq">Search</label><input id="sq" name="sq" />
<button id="search-btn" type="button">Find</button><div id="sresult" role="status"></div>
<label for="choice">Choice</label><select id="choice">
<option value="a">A</option><option value="b">B</option></select>
<div id="blurb">The quick brown fox.</div>
<div id="late" role="status"></div>
<a id="dl" href="/download">Get file</a>
</main><script>
document.getElementById('go').onclick = () => {
  document.getElementById('clicked').textContent = 'clicked';
};
document.getElementById('search-btn').onclick = () => {
  document.getElementById('sresult').textContent =
    'results for: ' + document.getElementById('sq').value;
};
setTimeout(() => { document.getElementById('late').textContent = 'arrived'; }, 300);
</script></body></html>"""

SECOND_HTML = "<!doctype html><html><body><main><h1>Second page</h1></main></body></html>"
DOWNLOAD_BYTES = b"hello download"


_MUTABLE = {"html": "<!doctype html><html><body><main></main></body></html>"}


def set_mutable(html: str) -> None:
    """Rewrite the /mutable page (Phase 6: simulate markup drift mid-test)."""
    _MUTABLE["html"] = html


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self) -> None:  # noqa: N802
        if self.path == "/mutable":
            body = _MUTABLE["html"].encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        if self.path == "/download":
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", 'attachment; filename="hello.txt"')
            self.send_header("Content-Length", str(len(DOWNLOAD_BYTES)))
            self.end_headers()
            self.wfile.write(DOWNLOAD_BYTES)
            return
        body = SECOND_HTML.encode() if self.path == "/second" else HOME_HTML.encode()
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args: object) -> None:
        pass


def serve() -> tuple[ThreadingHTTPServer, str]:
    """Start the fixture server; caller owns shutdown."""
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    return server, f"http://127.0.0.1:{server.server_port}/"
