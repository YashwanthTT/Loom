"""WebHermes TUI: five data pages over the SQLite store (Streamlit mirrors these)."""

from __future__ import annotations

import typer

from tau_agent.webhermes.config import load_config
from tau_coding.webhermes import queries

app = typer.Typer(
    name="webhermes", help="WebHermes deterministic web automation.", add_completion=False
)


@app.command()
def health() -> None:
    """Phase 0 health check: config loads, DB opens, no real features yet."""
    from tau_agent.webhermes.db import init_db, session
    from tau_agent.webhermes.models import Component

    cfg = load_config()
    init_db(":memory:")
    with session(":memory:") as s:
        s.add(Component(name="health", action_type="wait"))
    typer.echo(f"ok provider={cfg.provider} model={cfg.model} db=ok")


@app.command()
def dashboard() -> None:
    """Home: totals a non-technical observer can read at a glance."""
    st = queries.home_stats()
    typer.echo(
        f"components: {st['components']} (healthy {st['healthy']}, "
        f"degraded {st['degraded']}, broken {st['broken']})"
    )
    typer.echo(f"executions: {st['executions']} ({st['deterministic_runs']} deterministic)")
    typer.echo(f"failures: {st['failures']} ({st['recoveries']} recovered)")


@app.command()
def components() -> None:
    """Components with version, status, success rate; pass a name for history."""
    rows = queries.list_components()
    if not rows:
        typer.echo("(no components yet — discover one first)")
        return
    for r in rows:
        typer.echo(
            f"{r['name']} v{r['version']} [{r['status']}] "
            f"rate={r['success_rate']} {r['action']} domain={r['domain']}"
        )


@app.command()
def history(name: str = typer.Argument(..., help="Component name")) -> None:
    """Version history for one component (active version marked)."""
    rows = queries.component_history(name)
    if not rows:
        typer.echo(f"(unknown component {name!r})")
        return
    for r in rows:
        mark = "*" if r["active"] else " "
        typer.echo(f"{mark} v{r['version']} by={r['by']} {r['locator']} ({r['created']})")


@app.command()
def workflows() -> None:
    """Saved workflows with their step chains."""
    rows = queries.list_workflows()
    if not rows:
        typer.echo("(no workflows yet — run a task first)")
        return
    for r in rows:
        typer.echo(f"{r['name']} [{r['created_by']}]: {r['chain']}")


@app.command()
def executions(limit: int = typer.Option(20, "--limit", "-n")) -> None:
    """Recent runs: pass/fail per step, timing-agnostic, deterministic vs AI-assisted."""
    rows = queries.list_executions(limit)
    if not rows:
        typer.echo("(no executions yet)")
        return
    for r in rows:
        mode = "deterministic" if r["deterministic"] else f"ai-assisted ({r['llm_calls']} calls)"
        typer.echo(f"#{r['id']} {r['status']} {mode} workflow={r['workflow_id']}")
        for comp, method, ok in r["steps"]:
            typer.echo(f"    {'ok' if ok else 'FAIL'} {comp} [{method}]")


@app.command()
def failures(limit: int = typer.Option(20, "--limit", "-n")) -> None:
    """Failures with screenshots and the recovery narrative."""
    rows = queries.list_failures(limit)
    if not rows:
        typer.echo("(no failures — quiet is good)")
        return
    for r in rows:
        typer.echo(f"#{r['id']} {r['component']}: {r['error']} ({r['created']})")
        typer.echo(f"    {r['narrative']}")
        if r["screenshot"]:
            typer.echo(f"    shot: {r['screenshot']} dom: {r['dom']}")


if __name__ == "__main__":
    app()
