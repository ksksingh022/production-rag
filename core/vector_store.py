from pinecone import Pinecone, Index
from config import settings
from logger import get_logger

logger = get_logger("vector_store")

class VectorStoreManager:
    def __init__(self):
        self._client: Pinecone | None = None
        self._index: Index | None = None

    def _init_client(self) -> Pinecone:
        """Initializes the base Pinecone client using your API key."""
        if not self._client:
            if not settings.PINECONE_API_KEY:
                logger.error("PINECONE_API_KEY is missing from environment variables.")
                raise ValueError("Missing Pinecone configuration credentials.")
            
            # The modern client automatically resolves your cloud region via your API key
            self._client = Pinecone(api_key=settings.PINECONE_API_KEY)
            logger.info("Pinecone core engine initialized successfully.")
        return self._client

    def get_index(self) -> Index:
        """Returns a direct handle to your specific operational vector index."""
        if not self._index:
            client = self._init_client()
            index_name = settings.PINECONE_INDEX_NAME
            
            try:
                # Target the specific index where vectors are read and written
                self._index = client.Index(index_name)
                logger.info(f"Connected to Pinecone target index: '{index_name}'")
            except Exception as e:
                logger.error(f"Failed to access Pinecone index '{index_name}': {str(e)}")
                raise e
                
        return self._index

# Global vector store instance
vector_manager = VectorStoreManager()

if __name__ == "__main__":
    # Test the Pinecone connection
    try:
        index = vector_manager.get_index()
        print(f"Pinecone index '{settings.PINECONE_INDEX_NAME}' is accessible.")
        logger.info(f"Pinecone index '{settings.PINECONE_INDEX_NAME}' is accessible.")
    except Exception as e:
        print(f"Pinecone connection test failed: {str(e)}")
        logger.error(f"Pinecone connection test failed: {str(e)}")