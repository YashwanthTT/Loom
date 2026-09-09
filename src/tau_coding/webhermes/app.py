"""WebHermes TUI: one input, one streaming log. Nothing else.

Type a task ("get me the top 10 grossing films"), hit Enter — the app searches
the web itself, browses sources, and streams progress + the answer live.
`uv run tau` (no args) lands here.
"""

from __future__ import annotations

import asyncio
import queue

from textual.app import App, ComposeResult
from textual.widgets import Footer, Header, Input, RichLog


class WebHermesApp(App):
    TITLE = "WebHermes"
    BINDINGS = [("q", "quit", "Quit"), ("d", "toggle_dark", "Theme")]

    def __init__(self) -> None:
        super().__init__()
        self._queue: queue.Queue[str] = queue.Queue()
        self._task_running = False

    def compose(self) -> ComposeResult:
        yield Header()
        yield RichLog(id="log", wrap=True, highlight=True, auto_scroll=True)
        yield Input(placeholder="Ask anything — e.g. get me the top 10 grossing films", id="in")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one("#log", RichLog).write(
            "Ask anything. I search the web myself and stream what I find. (q quits)"
        )
        self.set_interval(0.1, self._drain)
        self.query_one("#in", Input).focus()

    def _drain(self) -> None:
        log = self.query_one("#log", RichLog)
        while True:
            try:
                log.write(self._queue.get_nowait())
            except queue.Empty:
                return

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        if event.input.id != "in" or self._task_running:
            return
        task = event.value.strip()
        if not task:
            return
        event.input.value = ""
        self._queue.put(f"> {task}")
        self._task_running = True
        self.run_worker(self._run(task))

    async def _run(self, task: str) -> None:
        try:
            await asyncio.to_thread(self._blocking_run, task, self._queue.put)
        except Exception as exc:  # noqa: BLE001 — worker must never die raw
            self._queue.put(f"ERROR: {type(exc).__name__}: {exc}")
        finally:
            self._task_running = False

    @staticmethod
    def _blocking_run(task: str, emit) -> None:
        """Research pipeline on a worker thread (blocking browser/LLM stay off-loop)."""
        from tau_agent.webhermes.browser import BrowserManager
        from tau_agent.webhermes.research import research
        from tau_agent.webhermes.stagehand.adapter import StagehandAdapter

        mgr = BrowserManager(headless=True)
        mgr.start()
        adapter = StagehandAdapter()
        try:
            ctx = mgr.new_session("tui")
            page = ctx.new_page()
            research(task, page=page, adapter=adapter, emit=emit)
        finally:
            adapter.close()
            mgr.stop()


def run_app() -> None:
    WebHermesApp().run()


if __name__ == "__main__":
    run_app()
