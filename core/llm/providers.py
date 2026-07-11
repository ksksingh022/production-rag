from typing import Iterator
from openai import OpenAI
from core.llm.base import BaseLLMEngine, LLMResponse, StreamChunk
from core.config import settings


class OpenAICompatibleEngine(BaseLLMEngine):
    """Single implementation shared by OpenAI, OpenRouter, and any local server
    (Ollama/vLLM) that speaks the OpenAI chat-completions wire format -- only the
    base_url/api_key differ, so one client class covers every provider."""

    def __init__(self, base_url: str | None, api_key: str | None, extra_headers: dict | None = None):
        self.client = OpenAI(
            base_url=base_url,
            api_key=api_key or "not-needed",
            timeout=settings.LLM_REQUEST_TIMEOUT_SECONDS,
        )
        self.extra_headers = extra_headers or {}

    def _messages(self, system_prompt: str, user_prompt: str) -> list[dict]:
        return [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

    def generate(self, system_prompt: str, user_prompt: str, model: str, max_tokens: int) -> LLMResponse:
        response = self.client.chat.completions.create(
            model=model,
            messages=self._messages(system_prompt, user_prompt),
            max_tokens=max_tokens,
            extra_headers=self.extra_headers,
        )
        choice = response.choices[0]
        usage = response.usage
        return LLMResponse(
            text=choice.message.content or "",
            prompt_tokens=usage.prompt_tokens if usage else 0,
            completion_tokens=usage.completion_tokens if usage else 0,
            model=model,
        )

    def stream(self, system_prompt: str, user_prompt: str, model: str, max_tokens: int) -> Iterator[StreamChunk]:
        stream = self.client.chat.completions.create(
            model=model,
            messages=self._messages(system_prompt, user_prompt),
            max_tokens=max_tokens,
            stream=True,
            # Providers that support it (OpenAI, OpenRouter) emit one extra chunk at the
            # end of the stream -- empty choices, populated usage -- when this is set.
            # Must keep iterating to the end of the stream to actually receive it.
            stream_options={"include_usage": True},
            extra_headers=self.extra_headers,
        )
        for chunk in stream:
            if chunk.choices:
                delta = chunk.choices[0].delta.content
                if delta:
                    yield StreamChunk(delta=delta)
            if chunk.usage:
                yield StreamChunk(usage={
                    "prompt_tokens": chunk.usage.prompt_tokens,
                    "completion_tokens": chunk.usage.completion_tokens,
                })
