from abc import ABC, abstractmethod

class BaseEmbeddingEngine(ABC):
    """Abstract Base Strategy for all Embedding Engines."""
    
    @abstractmethod
    def get_embedding(self, text: str) -> list[float]:
        """Takes a text string and returns its vector embedding list."""
        pass