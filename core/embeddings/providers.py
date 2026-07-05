from openai import OpenAI
from core.config import settings
from core.embeddings.base import BaseEmbeddingEngine

class OpenAIEmbeddingEngine(BaseEmbeddingEngine):
    """Strategy implementation for OpenAI Embeddings."""
    def __init__(self, model_name: str = "text-embedding-3-small"):
        self.client = OpenAI(api_key=settings.OPENAI_API_KEY)
        self.model_name = model_name

    def get_embedding(self, text: str) -> list[float]:
        response = self.client.embeddings.create(
            input=[text], 
            model=self.model_name
        )
        return response.data[0].embedding


class OllamaEmbeddingEngine(BaseEmbeddingEngine):
    """Strategy implementation for Local Ollama Embeddings."""
    def __init__(self, model_name: str = "nomic-embed-text"):
        # Setup local HTTP client here
        self.model_name = model_name

    def get_embedding(self, text: str) -> list[float]:
        # Imagine actual Ollama request logic here
        return [0.0] * 1536