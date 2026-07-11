from core.config import settings
from core.llm.base import BaseLLMEngine
from core.llm.providers import OpenAICompatibleEngine


class LLMFactory:
    """Factory Pattern resolving a provider name to a configured engine instance.
    Adding a new OpenAI-compatible provider is a one-line registration, no new class."""

    _instances: dict[str, BaseLLMEngine] = {}

    _PROVIDER_CONFIG = {
        "openrouter": lambda: {
            "base_url": "https://openrouter.ai/api/v1",
            "api_key": settings.OPENROUTER_API_KEY,
            "extra_headers": {"HTTP-Referer": "https://production-rag.local", "X-Title": settings.APP_NAME},
        },
        "openai": lambda: {"base_url": None, "api_key": settings.OPENAI_API_KEY},
        "local": lambda: {"base_url": settings.LOCAL_LLM_BASE_URL, "api_key": "not-needed"},
    }

    @classmethod
    def create(cls, provider: str) -> BaseLLMEngine:
        provider = provider.lower()
        if provider not in cls._PROVIDER_CONFIG:
            raise ValueError(f"Unknown LLM provider: '{provider}'. Known: {list(cls._PROVIDER_CONFIG)}")

        if provider not in cls._instances:
            config = cls._PROVIDER_CONFIG[provider]()
            cls._instances[provider] = OpenAICompatibleEngine(**config)

        return cls._instances[provider]

    @classmethod
    def register_provider(cls, name: str, config_fn):
        """Allows adding new OpenAI-compatible providers at runtime."""
        cls._PROVIDER_CONFIG[name.lower()] = config_fn
