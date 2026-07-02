import valkey
from config import settings
from logger import get_logger

logger = get_logger("valkey_cache")

class CacheManager:
    def __init__(self):
        self.client: valkey.Valkey | None = None

    def init_redis(self):
        """Initialize the Valkey connection pool securely for Aiven."""
        if not self.client:
            try:
                # Valkey.from_url automatically extracts SSL configuration from 'rediss://'
                self.client = valkey.Valkey.from_url(
                    settings.VALKEY_URL, 
                    decode_responses=True,       
                    socket_timeout=5.0,          
                    socket_connect_timeout=5.0,  
                    retry_on_timeout=True        
                )
                logger.info("Successfully connected to Aiven for Valkey.")
            except Exception as e:
                logger.error(f"Failed to connect to Valkey: {str(e)}")
                raise e

    def get_client(self) -> valkey.Valkey:
        if not self.client:
            self.init_redis()
        return self.client

# Global cache manager instance
cache_manager = CacheManager()

if __name__ == "__main__":
    # Test the Valkey connection
    try:
        cache_manager.init_redis()
        client = cache_manager.get_client()
        pong = client.ping()
        if pong:
            logger.info("Valkey connection test successful!")
        else:
            logger.error("Valkey connection test failed: No PONG response.")
    except Exception as e:
        logger.error(f"Valkey connection test failed: {str(e)}")