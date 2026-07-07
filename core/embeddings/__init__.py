from core.embeddings.factory import EmbeddingFactory

# Global instances initialized via our Factory Method Pattern
embedding_client = EmbeddingFactory.create(provider_name="openai", model_name="text-embedding-3-small")
local_embedding_client = EmbeddingFactory.create(provider_name="ollama", model_name="nomic-embed-text")
hf_embedding_client = EmbeddingFactory.create(provider_name="huggingface", model_name="all-MiniLM-L6-v2")

__all__ = [
    "embedding_client",
    "local_embedding_client",
    "hf_embedding_client"
]