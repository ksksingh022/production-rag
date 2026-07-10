from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "Production RAG"
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

    class Config:
        env_file = ".env"

settings = Settings()
