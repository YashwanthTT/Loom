"""Real Stagehand backend: own local Chromium + OpenCode model via LLM callback.

No Browserbase key, no first-party model key — `local_browser.launch()` starts a
correctly-wired browser, and the model callback routes inference through the
already-working tau_ai provider (OpenCode Go subscription).

All `stagehand` imports live in this package (boundary rule). Sync methods run
the async SDK on the adapter's portal loop.
"""

from __future__ import annotations

import json
from contextlib import suppress
from typing import Any

from pydantic import create_model


def make_llm_callback(config, on_call=None):
    """Wrap a WebHermesConfig in a Stagehand LLMGenerateCallback (text + images).

    `on_call(text, usage)` fires per completed call so the adapter can count tokens
    for Phase 12 metrics (real-backend LLM calls must not be invisible).
    """
    from uuid import uuid4

    from tau_agent.messages import ImageContent, TextContent, UserMessage
    from tau_agent.provider_events import AssistantDoneEvent, AssistantErrorEvent
    from tau_ai.env import OpenAICompatibleConfig
    from tau_ai.openai_compatible import OpenAICompatibleProvider

    session_id = uuid4().hex  # Go requires x-opencode-session per conversation

    async def _generate(policy_input: dict[str, Any]) -> dict[str, Any]:
        def _get(obj: Any, key: str, default: Any = None) -> Any:
            if isinstance(obj, dict):
                return obj.get(key, default)
            return getattr(obj, key, default)

        def _node(block: Any) -> Any:
            # Blocks arrive as RootModel wrappers (root=LLMTextContent(...)); unwrap first.
            inner = _get(block, "root", block)
            return inner if inner is not None else block

        def _blk(block: Any, key: str, default: Any = None) -> Any:
            return _get(_node(block), key, default)

        provider_cfg = config.to_provider_config()
        if provider_cfg is None:
            raise RuntimeError(f"no API key for provider={config.provider}")
        provider = OpenAICompatibleProvider(
            OpenAICompatibleConfig(
                api_key=provider_cfg.api_key,
                base_url=provider_cfg.base_url,
                timeout_seconds=provider_cfg.timeout_seconds,
                supports_images=True,  # stagehand sends screenshots
            )
        )
        texts, images = [], []
        for msg in _get(policy_input, "messages", []) or []:
            blocks = _get(msg, "content", [])
            if isinstance(blocks, dict) or not isinstance(blocks, list):
                blocks = [blocks]
            for b in blocks:
                if _blk(b, "type") == "text":
                    texts.append(_blk(b, "text", ""))
                elif _blk(b, "type") == "image":
                    images.append(
                        ImageContent(
                            data=_blk(b, "data", ""),
                            mime_type=_blk(b, "mime_type", "image/png"),
                        )
                    )
        system = _get(policy_input, "system_prompt") or ""
        fmt = _get(policy_input, "response_format") or {}
        structured = _get(fmt, "type") == "json_schema"
        if structured:
            system += "\nReply with ONLY JSON matching this exact schema, no fences."
            schema_obj = _get(fmt, "schema_", _get(fmt, "schema", _get(fmt, "json_schema", None)))
            if schema_obj is not None:
                with suppress(TypeError, ValueError):
                    system += "\nSchema:\n" + json.dumps(schema_obj, default=str)[:6000]
        content: Any = "\n".join(texts)
        if images:
            content = [TextContent(text=content or "(see attached screenshots)"), *images]
        try:
            async for event in provider.stream_response(
                model=config.model,
                system=system,
                messages=[UserMessage(content=content)],
                tools=[],
                session_id=session_id,
            ):
                if isinstance(event, AssistantDoneEvent):
                    if on_call is not None:
                        on_call(event.message.text, event.message.usage)
                    out: dict[str, Any] = {
                        "role": "assistant",
                        "content": {"type": "text", "text": event.message.text},
                        "stop_reason": "stop",
                        "usage": {
                            "input_tokens": event.message.usage.input,
                            "output_tokens": event.message.usage.output,
                            "total_tokens": event.message.usage.total_tokens,
                        },
                    }
                    if structured:
                        text = event.message.text
                        try:
                            start, end = text.index("{"), text.rindex("}") + 1
                            out["structured_content"] = json.loads(text[start:end])
                        except ValueError as exc:
                            raise RuntimeError(
                                f"model did not return JSON: {text[:200]!r}"
                            ) from exc
                        out["output_format"] = "json_schema"
                    return out
                if isinstance(event, AssistantErrorEvent):
                    raise RuntimeError(event.error.text or "provider error")
            raise RuntimeError("empty provider stream")
        finally:
            await provider.aclose()

    return _generate


class RealStagehand:
    """Sync facade over the real SDK (own browser, our model via callback).

    Stagehand owns its browser+pages here: per call we (re)navigate to the
    caller's URL, so observe/act/extract see the same page. Deterministic
    replay still runs on OUR browser — only AI steps live in this one.
    """

    def __init__(self, portal, config, on_llm_call=None, headless: bool = True) -> None:
        self._portal = portal
        self._config = config
        self._on_llm_call = on_llm_call
        self._headless = headless
        self._connected = False
        self._url = ""

    def _ensure(self) -> None:
        if self._connected:
            return
        self._portal.call(self._connect)
        self._connected = True

    async def _connect(self) -> None:
        from stagehand import Stagehand, local_browser

        browser = await local_browser.launch(headless=self._headless)
        callback = make_llm_callback(self._config, on_call=self._on_llm_call)
        self._sh = await Stagehand.create(browser=browser, model=callback)
        self._page = await self._sh.browser.context.new_page()

    async def _goto(self, url: str) -> Any:
        if url and url != self._url:
            await self._page.goto(url)
            self._url = url
        return self._page

    def close(self) -> None:
        if self._connected:
            self._portal.call(self._sh.close)
            self._connected = False

    # -- primitives (plain data in/out) ---------------------------------

    def observe(self, url: str, instruction: str) -> list[dict[str, Any]]:
        self._ensure()
        return self._portal.call(self._observe, url, instruction)

    async def _observe(self, url: str, instruction: str) -> list[dict[str, Any]]:
        page = await self._goto(url)
        result = await self._sh.observe(instruction, page=page)
        return [
            {
                "selector": a.selector,
                "description": a.description,
                "method": a.method,
                "arguments": a.arguments or [],
            }
            for a in result.data
        ]

    def act(self, url: str, instruction: str) -> dict[str, Any]:
        self._ensure()
        return self._portal.call(self._act, url, instruction)

    async def _act(self, url: str, instruction: str) -> dict[str, Any]:
        page = await self._goto(url)
        result = await self._sh.act(instruction, page=page)
        data = getattr(result, "data", result)
        detail = str(getattr(data, "message", "") or "")
        return {"success": bool(getattr(data, "success", False)), "detail": detail}

    def extract(self, url: str, instruction: str, schema: dict[str, Any]) -> dict[str, Any]:
        self._ensure()
        return self._portal.call(self._extract, url, instruction, schema)

    async def _extract(self, url: str, instruction: str, schema: dict[str, Any]) -> dict[str, Any]:
        from pydantic import BaseModel

        page = await self._goto(url)
        model = _schema_to_model(schema)
        result = await self._sh.extract(instruction, model, page=page)
        data = result.data
        if isinstance(data, BaseModel):
            return data.model_dump()
        return dict(data) if isinstance(data, dict) else {"value": data}


def _schema_to_model(schema: dict[str, Any]):
    """JSON-schema-ish dict → strict Pydantic model (all fields required-per-schema)."""
    props = schema.get("properties", {}) or {}
    required = set(schema.get("required", []) or [])
    fields = {}
    for name, spec in props.items():
        kind = (spec.get("type") if isinstance(spec, dict) else None) or "string"
        py = {"string": str, "integer": int, "number": float, "boolean": bool}.get(kind, str)
        fields[name] = (py, ... if name in required else None)
    return create_model("WebHermesExtract", **fields)
