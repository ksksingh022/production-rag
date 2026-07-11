from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "BridgeMind"
    DATABASE_URL: str
    VALKEY_URL: str
    PINECONE_API_KEY : str
    PINECONE_INDEX_NAME: str
    PINECONE_HOSTNAME: str
    LOG_LEVEL: str = "INFO"
    BM25_PARAMS_PATH: str = "core/embeddings/bm25_params.json"
    # Token-based chunk sizing (not chars) so chunks stay within the embedding model's
    # max sequence length. all-MiniLM-L6-v2 caps at 256 tokens -- keep a margin below it.
    CHUNK_SIZE_TOKENS: int = 200
    CHUNK_OVERLAP_TOKENS: int = 30

    # --- Query pipeline: retrieval ---
    PINECONE_NAMESPACE: str = "rag-documents"
    RETRIEVE_N: int = 20            # candidates fetched from Pinecone before rerank
    TOP_K: int = 5                  # final chunks returned to the LLM after rerank
    HYBRID_ALPHA: float = 0.5       # 0 = pure keyword/sparse, 1 = pure dense/semantic
    RERANK_ENABLED: bool = True
    RERANK_MODEL: str = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    # --- Query pipeline: caching ---
    CACHE_TTL_SECONDS: int = 3600
    PROMPT_VERSION: str = "v1"

    # --- Query pipeline: LLM (multi-provider, never locked to one model) ---
    LLM_DEFAULT_PROVIDER: str = "openrouter"
    # openrouter/free is OpenRouter's own router across its free-model pool -- zero LLM
    # spend, and it keeps working as individual free models rotate out (confirmed: the
    # specific free models once listed here, e.g. meta-llama/llama-3.1-8b-instruct:free,
    # have already been swapped out for a different lineup a few months later). Pinning a
    # specific free model id is just as fragile in the other direction (it 404s once its
    # free tier rotates off), so the router is still the better default despite the caveat
    # below -- services/generation.py adds a detector + retry to cover it.
    #
    # CAVEAT: the free router's pool has been observed to include content-moderation /
    # guard models (e.g. Llama Guard) alongside real chat models. Those don't answer
    # questions -- they output a safety classification like "User Safety: safe". See
    # services/generation.py's guard-output detector for the mitigation.
    LLM_DEFAULT_MODEL: str = "openrouter/free"
    LLM_ALLOWED_MODELS: list[str] = [
        "openrouter/free",
        "meta-llama/llama-3.1-8b-instruct:free",
        "google/gemini-flash-1.5:free",
        "gpt-4o-mini",
        "anthropic/claude-3.5-sonnet",
    ]
    LLM_MAX_OUTPUT_TOKENS: int = 800
    LLM_REQUEST_TIMEOUT_SECONDS: int = 60
    # Total attempts (including the first) before giving up when the model returns a
    # non-answer (e.g. a guard-model safety classification instead of a real response).
    LLM_MAX_ATTEMPTS: int = 3

    OPENROUTER_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    LOCAL_LLM_BASE_URL: str | None = None  # e.g. http://localhost:11434/v1 for Ollama

    # --- API ---
    API_KEY: str | None = None  # if set, required via X-API-Key header on /api/v1/*
    CORS_ORIGINS: list[str] = ["http://localhost:5173"]
    MAX_QUERY_LENGTH: int = 1000
    RATE_LIMIT_PER_MINUTE: int = 30

    class Config:
        env_file = ".env"

settings = Settings()
