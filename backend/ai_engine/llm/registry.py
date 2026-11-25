"""Build the configured language-model provider. Returns None when AI is switched off."""

from dataclasses import dataclass

from .base import LLMProvider


@dataclass(frozen=True)
class LLMConfig:
    provider: str  # none | anthropic | openai | ollama
    anthropic_model: str = "claude-opus-5-5"
    anthropic_api_key: str | None = None
    anthropic_effort: str = "high"
    openai_model: str = ""
    openai_api_key: str | None = None
    ollama_base_url: str = "http://localhost:11434/v1"
    ollama_model: str = ""
    timeout: float = 300.0


def build_provider(config: LLMConfig) -> LLMProvider | None:
    if config.provider == "none":
        return None
    if config.provider == "anthropic":
        from .anthropic_provider import AnthropicProvider

        return AnthropicProvider(config.anthropic_model, api_key=config.anthropic_api_key,
                                 effort=config.anthropic_effort, timeout=config.timeout)  # fmt: skip
    if config.provider == "openai":
        from .openai_provider import OpenAICompatibleProvider

        return OpenAICompatibleProvider("openai", config.openai_model, api_key=config.openai_api_key,
                                        timeout=config.timeout)  # fmt: skip
    if config.provider == "ollama":
        from .openai_provider import OpenAICompatibleProvider

        return OpenAICompatibleProvider("ollama", config.ollama_model, api_key=None,
                                        base_url=config.ollama_base_url, timeout=config.timeout)  # fmt: skip
    raise ValueError(f"Unknown LLM provider {config.provider}")


def describe(config: LLMConfig) -> tuple[str, str]:
    """(provider, model) for status displays, without building a client."""
    model = {
        "anthropic": config.anthropic_model,
        "openai": config.openai_model,
        "ollama": config.ollama_model,
    }.get(config.provider, "")
    return config.provider, model
