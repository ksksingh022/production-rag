from abc import ABC, abstractmethod

class BaseEmbeddingEngine(ABC):
    """Abstract Base Strategy for all Embedding Engines."""

    @abstractmethod
    def get_embedding(self, text: str) -> list[float]:
        """Takes a text string and returns its vector embedding list."""
        pass

    def get_embeddings(self, texts: list[str]) -> list[list[float]]:
        """Batch variant of get_embedding. Providers without native batch support fall back to a loop."""
        return [self.get_embedding(text) for text in texts]

    def get_tokenizer(self):
        """Returns the underlying tokenizer for token-aware text splitting, if the provider has one."""
        return None

    @property
    def max_tokens(self) -> int | None:
        """Max sequence length (in tokens) the model accepts, if known."""
        return None