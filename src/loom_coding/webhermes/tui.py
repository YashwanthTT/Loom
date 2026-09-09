"""Loom web commands: stagehand (AI browser) + selenium (plain browser)."""

from __future__ import annotations

import json

import typer

from loom_agent.tau_web.config import load_config

app = typer.Typer(name="web", help="Loom web automation: stagehand + selenium.", add_completion=False)


@app.command()
def health() -> None:
    """Config loads + which browser parts are importable."""
    cfg = load_config()
    try:
        import selenium  # noqa: F401

        selenium_ok = "ok"
    except ImportError:
        selenium_ok = "missing"
    try:
        import stagehand  # noqa: F401

        stagehand_ok = "ok"
    except ImportError:
        stagehand_ok = "missing"
    typer.echo(f"ok provider={cfg.provider} model={cfg.model} selenium={selenium_ok} stagehand={stagehand_ok}")


@app.command()
def browse(url: str = typer.Argument(..., help="URL to open with headless Chrome")) -> None:
    """Open a page with selenium and print its title + first text."""
    from loom_agent.tau_web.selenium.driver import SeleniumDriver

    driver = SeleniumDriver()
    try:
        page = driver.open(url)
    finally:
        driver.close()
    typer.echo(f"{page.title} ({page.url})")
    typer.echo(page.text[:1000])


@app.command()
def observe(
    url: str = typer.Argument(..., help="Page URL"),
    instruction: str = typer.Argument(..., help="Element to find, e.g. 'the search box'"),
) -> None:
    """Stagehand observe: print the CSS selector for `instruction` on `url`."""
    from loom_agent.tau_web.stagehand.adapter import StagehandAdapter

    adapter = StagehandAdapter()
    try:
        res = adapter.observe(url, instruction)
    finally:
        adapter.close()
    typer.echo(res.value if res.ok else f"error: {res.error}")
    if not res.ok:
        raise typer.Exit(1)


@app.command()
def act(
    url: str = typer.Argument(..., help="Page URL"),
    instruction: str = typer.Argument(..., help="Action, e.g. 'click the search button'"),
) -> None:
    """Stagehand act: perform `instruction` on `url`."""
    from loom_agent.tau_web.stagehand.adapter import StagehandAdapter

    adapter = StagehandAdapter()
    try:
        res = adapter.act(url, instruction)
    finally:
        adapter.close()
    typer.echo("ok" if res.ok else f"error: {res.error}")
    if not res.ok:
        raise typer.Exit(1)


@app.command()
def extract(
    url: str = typer.Argument(..., help="Page URL"),
    instruction: str = typer.Argument(..., help="What to extract, e.g. 'the page headline'"),
    field: str = typer.Option("value", "--field", "-f", help="Result field name"),
) -> None:
    """Stagehand extract: print one JSON field from `url`."""
    from loom_agent.tau_web.stagehand.adapter import StagehandAdapter

    adapter = StagehandAdapter()
    try:
        res = adapter.extract(url, instruction, {"properties": {field: {"type": "string"}}, "required": [field]})
    finally:
        adapter.close()
    if res.ok:
        typer.echo(json.dumps(json.loads(res.value), indent=2)[:2000])
    else:
        typer.echo(f"error: {res.error}")
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
