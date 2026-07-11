from fastapi import Header, HTTPException, status
from core.config import settings


async def require_api_key(x_api_key: str | None = Header(default=None)):
    """No-op if API_KEY isn't configured (local/dev). Once set, every /api/v1/* call
    must present a matching X-API-Key header."""
    if settings.API_KEY is None:
        return
    if x_api_key != settings.API_KEY:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key")
