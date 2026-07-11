from slowapi import Limiter
from slowapi.util import get_remote_address
from fastapi import Request


def _rate_limit_key(request: Request) -> str:
    # Prefer the API key (if auth is configured) over raw IP so a single client is
    # limited consistently even behind a shared NAT/proxy.
    api_key = request.headers.get("X-API-Key")
    return api_key or get_remote_address(request)


limiter = Limiter(key_func=_rate_limit_key)
