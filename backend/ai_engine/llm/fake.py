"""A scripted provider for tests. It is never selectable through configuration."""

from collections.abc import Callable
from typing import Any

from .base import LLMRequest, LLMResult

Response = dict[str, Any] | Exception | Callable[[LLMRequest], dict[str, Any]]


class ScriptedProvider:
    name = "scripted"
    model = "scripted-test-model"

    def __init__(self, responses: list[Response]) -> None:
        self.responses = list(responses)
        self.requests: list[LLMRequest] = []

    def complete_json(self, request: LLMRequest) -> LLMResult:
        self.requests.append(request)
        if not self.responses:
            raise AssertionError("ScriptedProvider ran out of responses")
        item = self.responses.pop(0)
        if isinstance(item, Exception):
            raise item
        data = item(request) if callable(item) else item
        return LLMResult(data=data, model=self.model, input_tokens=len(request.user) // 4, output_tokens=100,
                         stop_reason="end_turn")  # fmt: skip
