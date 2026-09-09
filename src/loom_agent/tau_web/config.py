"""LLM provider config: one `LLM_PROVIDER` toggle over loom_ai.env (all OpenAI-compatible).

Providers: `opencode` (default — your subscription), `openrouter`, `ollama`.
Never hardcoded — everything comes from env. See .env.example.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from loom_ai.env import (
    DEFAULT_OPENCODE_BASE_URL,
    DEFAULT_OPENCODE_MODEL,
    OpenAICompatibleConfig,
)

# (key_var, url_var, model_var, default_url, default_model) per provider.
_PROVIDER_DEFAULTS = {
    "opencode": (
        "OPENCODE_API_KEY",
        "OPENCODE_BASE_URL",
        "OPENCODE_MODEL",
        DEFAULT_OPENCODE_BASE_URL,
        DEFAULT_OPENCODE_MODEL,
    ),
    "openrouter": (
        "OPENROUTER_API_KEY",
        "OPENROUTER_BASE_URL",
        "OPENROUTER_MODEL",
        "https://openrouter.ai/api/v1",
        "anthropic/claude-sonnet-4",
    ),
    "ollama": (
        "OLLAMA_API_KEY",
        "OLLAMA_BASE_URL",
        "OLLAMA_MODEL",
        "http://localhost:11434/v1",
        "qwen2.5:7b",
    ),
}


@dataclass(frozen=True, slots=True)
class WebHermesConfig:
    provider: str
    model: str
    base_url: str
    api_key: str | None

    def to_provider_config(self) -> OpenAICompatibleConfig | None:
        """loom_ai provider config, or None when keyless (fake/dry-run)."""
        if not self.api_key:
            return None
        return OpenAICompatibleConfig(api_key=self.api_key, base_url=self.base_url.rstrip("/"))


def _load_dotenv() -> None:
    """Load .env if present (same search order as loom_coding.cli; no new dep)."""
    candidates = [
        Path.cwd() / ".env",
        Path(__file__).resolve().parents[2] / ".env",
        Path.home() / ".tau" / ".env",
    ]
    for p in candidates:
        if not p.is_file():
            continue
        try:
            for line in p.read_text(encoding="utf-8").splitlines():
                line = line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k, v = k.strip(), v.strip().strip('"').strip("'")
                if k and k not in os.environ:
                    os.environ[k] = v
        except OSError:
            continue


def load_config() -> WebHermesConfig:
    _load_dotenv()
    provider = os.environ.get("LLM_PROVIDER", "opencode").strip().lower()
    if provider not in _PROVIDER_DEFAULTS:
        raise RuntimeError(f"Unknown LLM_PROVIDER={provider!r}; want {sorted(_PROVIDER_DEFAULTS)}")
    key_var, url_var, model_var, default_url, default_model = _PROVIDER_DEFAULTS[provider]
    # Ollama usually needs no key; others do (validated lazily, not here).
    fallback = os.environ.get("OPENCODE_API_KEY") if provider == "opencode" else None
    return WebHermesConfig(
        provider=provider,
        model=os.environ.get(model_var, default_model),
        base_url=os.environ.get(url_var, default_url),
        api_key=os.environ.get(key_var) or fallback or ("ollama" if provider == "ollama" else None),
    )
