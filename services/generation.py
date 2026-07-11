import re
from dataclasses import dataclass
from typing import Iterator
from core.llm.factory import LLMFactory
from core.llm.base import StreamChunk
from core.llm.registry import resolve_provider, estimate_cost_usd
from core.config import settings
from core import get_logger
from services.retrieval import RetrievedChunk

logger = get_logger("generation_service")

SYSTEM_PROMPT = (
    "You are a helpful assistant that answers questions using ONLY the information in "
    "the provided context. Every claim in your answer must be grounded in the context. "
    "Answer in plain, natural prose -- do NOT include chunk ids, citation markers, or "
    "bracket references (e.g. [doc123#chunk_2]) anywhere in your answer text; the exact "
    "source chunks are already shown to the user separately. If the context does not "
    "contain enough information to answer, say you don't know instead of guessing or "
    "using outside knowledge."
)

# OpenRouter's free-model router draws from a pool that has been observed to include
# content-moderation / guard models (e.g. Llama Guard) alongside real chat models --
# those don't answer questions, they classify safety and output things like
# "User Safety: safe" or "unsafe\nS1,S3". This catches that shape so it's never
# silently returned to the user as if it were a real answer.
_GUARD_OUTPUT_PATTERNS = [
    re.compile(r"^\s*(user|response|prompt)\s+safety\s*:\s*(safe|unsafe)", re.IGNORECASE),
    re.compile(r"^\s*(safe|unsafe)\s*$", re.IGNORECASE),
    re.compile(r"^\s*unsafe\s*\n?\s*(s\d+)(\s*,\s*s\d+)*\s*$", re.IGNORECASE),
]
# Real answers to open-ended RAG questions run at least a sentence; every guard-model
# output seen in practice is well under this, so length is a cheap first filter before
# the (still fast) regex pass.
_GUARD_OUTPUT_MAX_LEN = 60


def _is_non_answer(text: str) -> bool:
    """True for anything that isn't a real answer: a blank/whitespace-only completion
    (models occasionally return one, independent of the guard-model issue) or a
    guard-model-shaped safety classification."""
    stripped = text.strip()
    if not stripped:
        return True
    if len(stripped) > _GUARD_OUTPUT_MAX_LEN:
        return False
    return any(p.match(stripped) for p in _GUARD_OUTPUT_PATTERNS)


class NonAnswerError(RuntimeError):
    """Raised when the model returns something that isn't an answer (e.g. a
    safety-classifier response) on every attempt."""
    pass


@dataclass
class GenerationResult:
    text: str
    prompt_tokens: int
    completion_tokens: int
    estimated_cost_usd: float | None
    provider: str
    model: str


class GenerationService:
    def _build_prompt(self, query: str, chunks: list[RetrievedChunk]) -> str:
        # chunk ids tag each block so the model can tell separate context pieces apart,
        # but SYSTEM_PROMPT instructs it not to reproduce them in the answer text.
        context_blocks = "\n\n".join(f"[{c.chunk_id}]\n{c.text}" for c in chunks)
        return f"Context:\n{context_blocks}\n\nQuestion: {query}\n\nAnswer:"

    def resolve(self, provider: str | None, model: str | None) -> tuple[str, str]:
        model = model or settings.LLM_DEFAULT_MODEL
        provider = resolve_provider(model, provider)
        return provider, model

    def generate(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        provider: str | None = None,
        model: str | None = None,
    ) -> GenerationResult:
        provider, model = self.resolve(provider, model)
        engine = LLMFactory.create(provider)
        user_prompt = self._build_prompt(query, chunks)

        last_text = ""
        for attempt in range(1, settings.LLM_MAX_ATTEMPTS + 1):
            response = engine.generate(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
                model=model,
                max_tokens=settings.LLM_MAX_OUTPUT_TOKENS,
            )
            if not _is_non_answer(response.text):
                cost = estimate_cost_usd(model, response.prompt_tokens, response.completion_tokens)
                return GenerationResult(
                    text=response.text,
                    prompt_tokens=response.prompt_tokens,
                    completion_tokens=response.completion_tokens,
                    estimated_cost_usd=cost,
                    provider=provider,
                    model=model,
                )
            last_text = response.text
            logger.warning(
                f"Model '{model}' returned a non-answer on attempt {attempt}/{settings.LLM_MAX_ATTEMPTS}: {response.text!r}"
            )

        raise NonAnswerError(
            f"The model repeatedly returned a non-answer (e.g. a content-safety classification "
            f"instead of a response) after {settings.LLM_MAX_ATTEMPTS} attempts: {last_text!r}"
        )

    def stream(
        self,
        query: str,
        chunks: list[RetrievedChunk],
        provider: str | None = None,
        model: str | None = None,
    ) -> Iterator[StreamChunk]:
        provider, model = self.resolve(provider, model)
        engine = LLMFactory.create(provider)
        user_prompt = self._build_prompt(query, chunks)

        for attempt in range(1, settings.LLM_MAX_ATTEMPTS + 1):
            # Buffer chunks until either enough text has arrived to be confident this
            # isn't a (always-short) guard-model output, or the stream ends -- so a
            # guard response never reaches the client mid-stream before we can tell.
            buffer: list[StreamChunk] = []
            buffered_text = ""
            usage_chunk: StreamChunk | None = None
            flushed = False

            for chunk in engine.stream(
                system_prompt=SYSTEM_PROMPT,
                user_prompt=user_prompt,
                model=model,
                max_tokens=settings.LLM_MAX_OUTPUT_TOKENS,
            ):
                if chunk.usage:
                    usage_chunk = chunk
                    continue
                if flushed:
                    yield chunk
                    continue
                buffer.append(chunk)
                buffered_text += chunk.delta or ""
                if len(buffered_text) > _GUARD_OUTPUT_MAX_LEN:
                    yield from buffer
                    flushed = True

            if flushed:
                if usage_chunk:
                    yield usage_chunk
                return

            if not _is_non_answer(buffered_text):
                yield from buffer
                if usage_chunk:
                    yield usage_chunk
                return

            logger.warning(
                f"Model '{model}' returned a non-answer on streaming attempt "
                f"{attempt}/{settings.LLM_MAX_ATTEMPTS}: {buffered_text!r}"
            )

        raise NonAnswerError(
            f"The model repeatedly returned a non-answer (e.g. a content-safety classification "
            f"instead of a response) after {settings.LLM_MAX_ATTEMPTS} attempts."
        )


generation_service = GenerationService()
