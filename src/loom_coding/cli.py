"""Minimal CLI for learning: harness + simple print loop.

This is a stripped-down replacement for the full Loom CLI.

What it teaches (maps to Pi architecture):
  loom_coding/cli.py  -> simple frontend (this file)
  loom_agent/harness.py + loop.py -> reusable brain
  loom_ai/fake.py or openai_compatible.py -> provider layer
  loom_coding/tools.py -> filesystem/shell tools

Keep the core independent: no Textual, no sessions, no OAuth, no extensions.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from uuid import uuid4

import anyio
import typer
from loom_ai.env import DEFAULT_OPENCODE_BASE_URL, DEFAULT_OPENCODE_MODEL

# Stable per-process conversation id for OpenCode Go routing/cache affinity
# (https://opencode.ai/docs/go requires x-opencode-session per conversation).
_CLI_SESSION_ID = uuid4().hex


def _load_dotenv() -> None:
    """Load .env if present (simple parser, no external dep)."""
    # Search: cwd/.env, repo-root/.env, ~/.loom/.env
    candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parents[2] / ".env",
        Path.home() / ".loom" / ".env",
    ]
    for p in candidates:
        if not p.is_file():
            continue
        try:
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                # Do not override already exported vars
                if k and k not in os.environ:
                    os.environ[k] = v
        except Exception:
            continue


_load_dotenv()

from loom_agent import AgentHarness, AgentHarnessConfig
from loom_agent.events import AgentEvent, MessageEndEvent, MessageUpdateEvent, ToolExecutionEndEvent
from loom_coding.tools import create_coding_tools
from loom_coding.webhermes.tui import app as webhermes_app

app = typer.Typer(
    name="loom",
    help="Minimal Loom harness for learning - harness + simple CLI + tools.",
    add_completion=False,
)
app.add_typer(webhermes_app, name="web")


@app.callback(invoke_without_command=True)
def _default(ctx: typer.Context) -> None:
    """No command ⇒ chat REPL (the chat interface is the product)."""
    if ctx.invoked_subcommand is None:
        _repl(Path.cwd(), None, "You are a helpful coding agent. Use read/write/edit/bash tools as needed.")


def _resolve_provider(model: str | None):
    """Resolve a ModelProvider. Uses env if available, else FakeProvider."""
    # Priority: OPENCODE_API_KEY (and ZEN_API_KEY alias) > OPENAI_API_KEY
    # OpenCode Go: https://opencode.ai/zen/go/v1 (see https://opencode.ai/docs/go).
    # Model ids use `opencode-go/<model-id>`, e.g. opencode-go/kimi-k3.
    opencode_key = os.environ.get("OPENCODE_API_KEY") or os.environ.get("ZEN_API_KEY")
    openai_key = os.environ.get("OPENAI_API_KEY")
    # Determine if we should use opencode gateway
    use_opencode = opencode_key is not None
    # Allow explicit opencode model prefix like "opencode-go/kimi-k3" or
    # "opencode/muse-spark-..." to force opencode even without key env?
    # Check model hint as fallback
    if model and (model.startswith("opencode/") or model.startswith("opencode-go/")):
        use_opencode = True

    if use_opencode and opencode_key:
        api_key = opencode_key
        base_url = (
            os.environ.get("OPENCODE_BASE_URL")
            or os.environ.get("ZEN_BASE_URL")
            or os.environ.get("OPENAI_BASE_URL")
            or DEFAULT_OPENCODE_BASE_URL
        )
        # Model priority: explicit arg > OPENCODE_MODEL > ZEN_MODEL > LOOM_MODEL > Go default
        raw_model = model or os.environ.get("OPENCODE_MODEL") or os.environ.get("ZEN_MODEL") or os.environ.get("LOOM_MODEL") or DEFAULT_OPENCODE_MODEL
        # Strip provider prefix like "opencode-go/kimi-k3" -> "kimi-k3"
        chosen_model = raw_model.split("/")[-1] if "/" in raw_model else raw_model
        # Go responses-path models (opencode.ai/docs/go#endpoints); rest use chat.
        lowered = chosen_model.lower()
        use_responses = (
            "muse-spark" in lowered or "codex" in lowered or lowered.startswith(("grok-4", "gpt-5.6-luna", "gpt-5.5", "gpt-5.4"))
        )
        # Anthropic /messages Go models (minimax-*, qwen3.*) are not supported
        # by this OpenAI-compatible provider; fail fast with a clear message.
        if lowered.startswith(("minimax-", "qwen3.")):
            typer.echo(
                f"Model '{chosen_model}' needs the Anthropic /messages Go endpoint, "
                "which this agent does not support. Use a chat/responses Go model.",
                err=True,
            )
            raise typer.Exit(2)
        api = "openai-responses" if use_responses else "openai-completions"
        from loom_ai.env import OpenAICompatibleConfig
        from loom_ai.openai_compatible import OpenAICompatibleProvider

        config = OpenAICompatibleConfig(
            base_url=base_url.rstrip("/"),
            api_key=api_key,
            timeout_seconds=60,
            api=api,
            provider_name="opencode-go" if "/zen/go" in base_url else "opencode",
        )
        try:
            provider = OpenAICompatibleProvider(config)
            return provider, chosen_model
        except Exception as exc:  # noqa: BLE001
            typer.echo(f"Could not create OpenCode provider ({exc}), falling back to fake.", err=True)
    elif openai_key:
        api_key = openai_key
        base_url = os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1")
        chosen_model = model or os.environ.get("LOOM_MODEL", "gpt-4o-mini")
        from loom_ai.env import OpenAICompatibleConfig
        from loom_ai.openai_compatible import OpenAICompatibleProvider

        config = OpenAICompatibleConfig(
            base_url=base_url,
            api_key=api_key,
            timeout_seconds=60,
        )
        # OpenAICompatibleProvider in loom_ai expects provider config object,
        # but we can use the simpler adapter if available; fallback to fake
        try:
            provider = OpenAICompatibleProvider(config)
            return provider, chosen_model
        except Exception as exc:  # noqa: BLE001
            typer.echo(f"Could not create OpenAI provider ({exc}), falling back to fake.", err=True)
    else:
        # No key set - will fall through to fake provider below
        raw = model or os.environ.get("OPENCODE_MODEL") or os.environ.get("LOOM_MODEL", "gpt-4o-mini")
        chosen_model = raw.split("/")[-1] if "/" in raw else raw

    # Fallback: deterministic fake provider for offline learning
    from loom_agent.messages import AssistantMessage, TextContent
    from loom_agent.provider_events import AssistantDoneEvent, AssistantStartEvent, TextDeltaEvent
    from loom_ai.fake import FakeProvider

    if opencode_key is not None or "OPENCODE_MODEL" in os.environ:
        help_text = f"Hello from minimal Loom! Set OPENCODE_API_KEY and OPENCODE_MODEL={DEFAULT_OPENCODE_MODEL} for real Go model calls (or OPENAI_API_KEY for OpenAI)."
    else:
        help_text = "Hello from minimal Loom! Set OPENCODE_API_KEY for real Go model calls (or OPENAI_API_KEY)."
    msg = AssistantMessage(
        model=chosen_model,
        content=[TextContent(text=help_text)],
        stop_reason="stop",
    )
    partial = AssistantMessage(model=chosen_model, content=[TextContent(text="")])
    stream = [
        AssistantStartEvent(partial=partial),
        TextDeltaEvent(content_index=0, delta=help_text, partial=partial),
        AssistantDoneEvent(reason="stop", message=msg),
    ]
    provider = FakeProvider(streams=[stream])
    return provider, chosen_model


def _print_event(event: AgentEvent) -> None:
    """Simple renderer for learning - just print text and tool calls."""
    if isinstance(event, MessageUpdateEvent):
        # streaming delta
        delta = event.assistant_message_event
        text = getattr(delta, "delta", None)
        if text:
            print(text, end="", flush=True)
    elif isinstance(event, MessageEndEvent):
        msg = event.message
        # msg.text is the visible text
        if hasattr(msg, "text") and msg.text and msg.role == "assistant":
            # already streamed via deltas, just newline
            print()
        elif msg.role == "user":
            pass
        elif msg.role == "toolResult":
            print(f"\n[tool {msg.tool_name} -> {'error' if msg.is_error else 'ok'}] {msg.text[:500]}")
    elif isinstance(event, ToolExecutionEndEvent):
        status = "error" if event.is_error else "ok"
        print(f"\n[tool {event.tool_name} {status}]")


async def _run_prompt(prompt: str, cwd: Path, model: str | None, system: str) -> bool:
    provider, resolved_model = _resolve_provider(model)
    tools = create_coding_tools(cwd=cwd)

    harness = AgentHarness(
        AgentHarnessConfig(
            provider=provider,
            model=resolved_model,
            system=system,
            tools=tools,
            session_id=_CLI_SESSION_ID,
        )
    )

    ok = True
    async for event in harness.prompt(prompt):
        _print_event(event)
        # detect error stop
        if isinstance(event, MessageEndEvent) and getattr(event.message, "stop_reason", None) == "error":
            ok = False
    return ok


def _repl(cwd: Path, model: str | None, system: str) -> None:
    """Chat REPL: read line -> harness -> tools -> print events."""
    typer.echo(f"Loom chat (model={model or 'auto'}, cwd={cwd})")
    typer.echo("Type a prompt, or 'quit' to exit. Example: explain this repo")
    while True:
        try:
            user_input = input("\n> ").strip()
        except (EOFError, KeyboardInterrupt):
            break
        if not user_input or user_input.lower() in {"quit", "exit", "q"}:
            break
        anyio.run(_run_prompt, user_input, cwd, model, system)


@app.command()
def main(
    prompt: str = typer.Argument(None, help="Prompt to send (or omit for REPL)"),
    model: str = typer.Option(None, "--model", "-m", help="Model name"),
    cwd: Path = typer.Option(Path.cwd(), "--cwd", help="Working directory for tools"),
    system: str = typer.Option("You are a helpful coding agent. Use read/write/edit/bash tools as needed.", "--system", help="System prompt"),
    print_mode: bool = typer.Option(False, "--print", "-p", help="One-shot print mode (no REPL)"),
) -> None:
    """Minimal harness: prompt -> loop -> tools -> print events."""
    if prompt and print_mode:
        ok = anyio.run(_run_prompt, prompt, cwd, model, system)
        raise typer.Exit(0 if ok else 1)

    if prompt and not print_mode:
        # single prompt then REPL
        anyio.run(_run_prompt, prompt, cwd, model, system)

    _repl(cwd, model, system)


if __name__ == "__main__":
    app()
