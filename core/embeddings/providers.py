from sentence_transformers import SentenceTransformer  # HuggingFace local models ke liye
from core.config import settings
from core.embeddings.base import BaseEmbeddingEngine


class HuggingFaceEmbeddingEngine(BaseEmbeddingEngine):
    """Strategy implementation for Local HuggingFace Embeddings using SentenceTransformers."""
    def __init__(self, model_name: str = "all-MiniLM-L6-v2"):
        self.model_name = model_name
        # Jab class initialize hogi, model local memory/cache mein load ho jayega
        self.model = SentenceTransformer(model_name)

    def get_embedding(self, text: str) -> list[float]:
        # convert_to_numpy=False karke direct python list nikalte hain standard format ke liye
        embedding = self.model.encode(text, convert_to_numpy=True)
        return embedding.tolist()


class OllamaEmbeddingEngine(BaseEmbeddingEngine):
    """Strategy implementation for Local Ollama Embeddings."""
    def __init__(self, model_name: str = "nomic-embed-text"):
        self.model_name = model_name

    def get_embedding(self, text: str) -> list[float]:
        return [0.0] * 1536