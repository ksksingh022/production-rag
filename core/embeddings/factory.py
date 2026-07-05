from typing import Type
from core.embeddings.base import BaseEmbeddingEngine
from core.embeddings.providers import OpenAIEmbeddingEngine, OllamaEmbeddingEngine

class EmbeddingFactory:
    """Factory Pattern to handle dynamic resolution of embedding providers."""
    
    # Registering our engines inside a dynamic dictionary map
    _registry: dict[str, Type[BaseEmbeddingEngine]] = {
        "openai": OpenAIEmbeddingEngine,
        "ollama": OllamaEmbeddingEngine
    }

    @classmethod
    def register_provider(cls, name: str, engine_class: Type[BaseEmbeddingEngine]):
        """Allows adding new engines at runtime without modifying this class."""
        cls._registry[name.lower()] = engine_class

    @classmethod
    def create(cls, provider_name: str, model_name: str | None = None) -> BaseEmbeddingEngine:
        """Factory Method resolving the actual engine object."""
        engine_class = cls._registry.get(provider_name.lower())
        if not engine_class:
            raise ValueError(f"Unknown embedding provider: '{provider_name}'.")
        
        # Instantiate with fallback to defaults if model_name isn't provided
        return engine_class(model_name) if model_name else engine_class()