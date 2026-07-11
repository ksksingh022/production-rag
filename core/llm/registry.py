from core.config import settings

# Model catalog: id -> {provider, context_window, input $/1k tokens, output $/1k tokens}.
# Free-tier models have $0 rates. Extend this as LLM_ALLOWED_MODELS grows -- the query
# pipeline never hardcodes a model, it only ever reads from here + config/the request.
MODEL_REGISTRY: dict[str, dict] = {
    "openrouter/free": {
        # Router across OpenRouter's free-model pool -- context window varies by which
        # underlying model gets picked per-request, so this is a conservative floor, not
        # a hard cap enforced by OpenRouter itself.
        "provider": "openrouter", "context_window": 8192, "input_per_1k": 0.0, "output_per_1k": 0.0,
    },
    "meta-llama/llama-3.1-8b-instruct:free": {
        "provider": "openrouter", "context_window": 131072, "input_per_1k": 0.0, "output_per_1k": 0.0,
    },
    "google/gemini-flash-1.5:free": {
        "provider": "openrouter", "context_window": 1000000, "input_per_1k": 0.0, "output_per_1k": 0.0,
    },
    "gpt-4o-mini": {
        "provider": "openai", "context_window": 128000, "input_per_1k": 0.00015, "output_per_1k": 0.0006,
    },
    "anthropic/claude-3.5-sonnet": {
        "provider": "openrouter", "context_window": 200000, "input_per_1k": 0.003, "output_per_1k": 0.015,
    },
}


def get_model_info(model_id: str) -> dict | None:
    return MODEL_REGISTRY.get(model_id)


def resolve_provider(model_id: str, requested_provider: str | None = None) -> str:
    """Explicit request wins; otherwise infer from the registry; otherwise fall back to the default."""
    if requested_provider:
        return requested_provider
    info = get_model_info(model_id)
    if info:
        return info["provider"]
    return settings.LLM_DEFAULT_PROVIDER


def estimate_cost_usd(model_id: str, prompt_tokens: int, completion_tokens: int) -> float | None:
    info = get_model_info(model_id)
    if not info:
        return None
    return (prompt_tokens / 1000) * info["input_per_1k"] + (completion_tokens / 1000) * info["output_per_1k"]
