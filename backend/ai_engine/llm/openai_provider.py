"""OpenAI, and any OpenAI-compatible server such as Ollama, via the official OpenAI Python SDK."""

import json

import openai

from .base import LLMError, LLMRequest, LLMResult


class OpenAICompatibleProvider:
    def __init__(
        self, name: str, model: str, *, api_key: str | None, base_url: str | None = None, timeout: float = 300.0
    ) -> None:
        if not model:
            raise ValueError(f"Set the model name for the {name} provider (OPENAI_MODEL or OLLAMA_MODEL).")
        self.name = name
        self.model = model
        # Ollama ignores the key but the SDK requires one.
        self._client = openai.OpenAI(
            api_key=api_key or ("ollama" if name == "ollama" else None),
            base_url=base_url,
            timeout=timeout,
            max_retries=2,
        )

    def complete_json(self, request: LLMRequest) -> LLMResult:
        try:
            response = self._client.chat.completions.create(
                model=self.model,
                max_completion_tokens=request.max_output_tokens,
                messages=[
                    {"role": "system", "content": request.system},
                    {"role": "user", "content": request.user},
                ],
                response_format={
                    "type": "json_schema",
                    "json_schema": {"name": request.schema_name, "schema": request.schema, "strict": True},
                },
            )
        except openai.AuthenticationError as exc:
            raise LLMError(f"{self.name} rejected the API key.", retryable=False) from exc
        except openai.NotFoundError as exc:
            raise LLMError(f"Model {self.model} was not found on {self.name}.", retryable=False) from exc
        except openai.BadRequestError as exc:
            raise LLMError(f"{self.name} rejected the request: {exc.message}", retryable=False) from exc
        except openai.RateLimitError as exc:
            raise LLMError(f"{self.name} rate limit reached; the job will retry.", retryable=True) from exc
        except openai.APIStatusError as exc:
            raise LLMError(f"{self.name} API error {exc.status_code}.", retryable=exc.status_code >= 500) from exc
        except openai.APIConnectionError as exc:
            raise LLMError(f"Could not reach {self.name}; the job will retry.", retryable=True) from exc

        choice = response.choices[0]
        if choice.finish_reason == "length":
            raise LLMError("The model's answer was cut off. Extract from fewer documents at a time.", retryable=False)
        refusal = getattr(choice.message, "refusal", None)
        if refusal:
            raise LLMError(f"The model declined this content: {refusal}", retryable=False)
        try:
            data = json.loads(choice.message.content or "")
        except json.JSONDecodeError as exc:
            raise LLMError("The model returned invalid JSON.", retryable=False) from exc
        usage = response.usage
        return LLMResult(
            data=data,
            model=response.model,
            input_tokens=usage.prompt_tokens if usage else 0,
            output_tokens=usage.completion_tokens if usage else 0,
            stop_reason=choice.finish_reason,
            provider_request_id=getattr(response, "id", None),
        )
