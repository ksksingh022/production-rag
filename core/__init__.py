from config import settings
from logger import setup_logging, get_logger
from database import get_db, Base
from cache import cache_manager
from vector_store import vector_manager

setup_logging()
logger = get_logger("core_init")
logger.info(f"Initializing core utilities for {settings.APP_NAME}")

__all__ = [
    "settings",
    "get_db",
    "Base",
    "cache_manager",
    "vector_manager",
    "get_logger"
]