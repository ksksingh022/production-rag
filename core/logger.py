import logging
import sys
from config import settings

def setup_logging():
    """Configures the root logger for the application."""
    log_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    
    logging.basicConfig(
        level=settings.LOG_LEVEL.upper(),
        format=log_format,
        handlers=[
            logging.StreamHandler(sys.stdout) # Outputs to console/Docker logs
        ]
    )

def get_logger(name: str) -> logging.Logger:
    """Helper function to get a named logger instance."""
    return logging.getLogger(name)