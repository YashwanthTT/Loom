"""Phase 1: structured results never leak raw exceptions (no browser needed)."""

from __future__ import annotations

from tau_agent.webhermes.browser import ActionExecutor, ActionResult
from tau_agent.webhermes.browser.results import run


def test_run_ok() -> None:
    res = run("click", lambda: None)
    assert res == ActionResult(ok=True, action="click", duration_ms=res.duration_ms)


def test_run_converts_exception() -> None:
    def boom() -> None:
        raise TimeoutError("waiting for selector")

    res = run("click", boom)
    assert not res.ok
    assert res.error_type == "TimeoutError"
    assert "waiting for selector" in (res.error or "")


def test_executor_failure_is_data_not_raise() -> None:
    class _DeadPage:
        def click(self, *args: object, **kwargs: object) -> None:
            raise ConnectionError("browser closed")

        def fill(self, *args: object, **kwargs: object) -> None:
            raise ConnectionError("browser closed")

        def text_content(self, *args: object, **kwargs: object) -> None:
            raise ConnectionError("browser closed")

        def wait_for_selector(self, *args: object, **kwargs: object) -> None:
            raise ConnectionError("browser closed")

    ex = ActionExecutor(_DeadPage())  # type: ignore[arg-type]
    for res in (ex.click("#x"), ex.fill("#x", "y"), ex.read_text("#x"), ex.wait_for("#x")):
        assert not res.ok and res.error_type == "ConnectionError"
