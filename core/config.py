from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "Production RAG"
    DATABASE_URL: str 
    VALKEY_URL: str
    PINECONE_API_KEY : str
    PINECONE_INDEX_NAME: str
    PINECONE_HOSTNAME: str
    LOG_LEVEL: str = "INFO"

    class Config:
        env_file = ".env"

settings = Settings()
