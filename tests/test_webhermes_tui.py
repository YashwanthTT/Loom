"""TUI: input in, streamed lines out. Research itself is unit-tested elsewhere."""

from __future__ import annotations

import pytest
from textual.widgets import Input, RichLog

from tau_coding.webhermes.app import WebHermesApp


@pytest.mark.anyio
async def test_boots_with_input_and_log() -> None:
    app = WebHermesApp()
    async with app.run_test() as pilot:
        assert app.query_one("#in", Input) is not None
        assert app.query_one("#log", RichLog) is not None
        await pilot.pause()


@pytest.mark.anyio
async def test_submit_streams_worker_lines(monkeypatch: pytest.MonkeyPatch) -> None:
    def _fake_run(task: str, emit) -> None:
        emit("searching the web for: films")
        emit("1. Avatar — $2.9B")

    monkeypatch.setattr(WebHermesApp, "_blocking_run", staticmethod(_fake_run))
    app = WebHermesApp()
    async with app.run_test() as pilot:
        app.query_one("#in", Input).value = "top 10 grossing films"
        await pilot.press("enter")
        for _ in range(100):
            await pilot.pause()
            texts = [line.text for line in app.query_one("#log", RichLog).lines]
            if any("Avatar" in t for t in texts):
                break
        else:
            raise AssertionError("streamed lines never appeared")
        assert any("> top 10 grossing films" in t for t in texts)
