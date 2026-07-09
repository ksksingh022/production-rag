from core.embeddings.factory import EmbeddingFactory

# Global instances initialized via our Factory Method Pattern
local_embedding_client = EmbeddingFactory.create(provider_name="ollama", model_name="nomic-embed-text")
hf_embedding_client = EmbeddingFactory.create(provider_name="huggingface", model_name="all-MiniLM-L6-v2")

__all__ = [
    "local_embedding_client",
    "hf_embedding_client"
]