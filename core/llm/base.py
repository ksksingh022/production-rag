from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Iterator


@dataclass
class LLMResponse:
    text: str
    prompt_tokens: int
    completion_tokens: int
    model: str


@dataclass
class StreamChunk:
    """One item from a streaming completion. Either a text delta, or (typically the
    final item) token usage -- providers that support it (e.g. OpenAI-compatible APIs
    with stream_options.include_usage) emit a usage-only chunk once the stream ends."""
    delta: str | None = None
    usage: dict | None = None  # {"prompt_tokens": int, "completion_tokens": int}


class BaseLLMEngine(ABC):
    """Abstract Strategy for all LLM providers. Every provider takes a system + user
    prompt and a model id -- the model is never baked into the engine itself, so the
    same engine instance can serve any model that provider hosts."""

    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str, model: str, max_tokens: int) -> LLMResponse:
        """Single-shot completion."""
        pass

    @abstractmethod
    def stream(self, system_prompt: str, user_prompt: str, model: str, max_tokens: int) -> Iterator[StreamChunk]:
        """Yields StreamChunks (text deltas, plus a final usage chunk when the provider
        supports it) for SSE streaming to the client."""
        pass
