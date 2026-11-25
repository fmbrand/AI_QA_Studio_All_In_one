"""The provider-independent language-model interface. Business code depends only on this module."""

from dataclasses import dataclass, field
from typing import Any, Protocol


class LLMError(Exception):
    """A model call failed. `retryable` says whether trying again later may succeed (rate limit,
    overload, network) or not (bad credentials, refusal, invalid request)."""

    def __init__(self, message: str, *, retryable: bool, provider_request_id: str | None = None) -> None:
        super().__init__(message)
        self.retryable = retryable
        self.provider_request_id = provider_request_id


@dataclass
class LLMResult:
    data: dict[str, Any]
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    stop_reason: str | None = None
    provider_request_id: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)


@dataclass
class LLMRequest:
    """One structured-output call: a stable system prompt, one user message, a JSON schema for the reply."""

    system: str
    user: str
    schema: dict[str, Any]
    schema_name: str
    max_output_tokens: int = 16000


class LLMProvider(Protocol):
    name: str
    model: str

    def complete_json(self, request: LLMRequest) -> LLMResult: ...
