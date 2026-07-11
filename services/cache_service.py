import hashlib
import json
import re
from core import cache_manager, get_logger
from core.config import settings

logger = get_logger("query_cache_service")

CACHE_EPOCH_KEY = "cache_epoch:rag-documents"


def _normalize_query(query: str) -> str:
    return re.sub(r"\s+", " ", query.strip().lower())


class QueryCacheService:
    """Exact-match query cache in Valkey. Keys are versioned by a cache epoch that's
    bumped on every successful ingest, so stale answers age out automatically when the
    underlying corpus changes -- no need to flush the whole cache by hand."""

    def __init__(self):
        self.client = cache_manager.get_client()

    def _current_epoch(self) -> str:
        return self.client.get(CACHE_EPOCH_KEY) or "0"

    def bump_epoch(self):
        self.client.incr(CACHE_EPOCH_KEY)

    def _build_key(self, query: str, filters: dict | None, top_k: int, provider: str, model: str) -> str:
        normalized = _normalize_query(query)
        filters_str = json.dumps(filters or {}, sort_keys=True)
        epoch = self._current_epoch()
        raw = f"{epoch}:{settings.PROMPT_VERSION}:{normalized}:{filters_str}:{top_k}:{provider}:{model}"
        digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
        return f"qcache:{digest}"

    def get(self, query: str, filters: dict | None, top_k: int, provider: str, model: str) -> dict | None:
        key = self._build_key(query, filters, top_k, provider, model)
        raw = self.client.get(key)
        if not raw:
            return None
        try:
            return json.loads(raw)
        except json.JSONDecodeError:
            logger.warning(f"Corrupt cache entry at {key}, ignoring.")
            return None

    def set(self, query: str, filters: dict | None, top_k: int, provider: str, model: str, response: dict):
        key = self._build_key(query, filters, top_k, provider, model)
        self.client.setex(key, settings.CACHE_TTL_SECONDS, json.dumps(response))


query_cache_service = QueryCacheService()
