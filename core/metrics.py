from prometheus_client import Counter, Histogram

# Exposed at /metrics (wired via prometheus-fastapi-instrumentator in main.py), scraped
# by Prometheus. Labels kept low-cardinality (stage/type names, not raw query text).

QUERY_LATENCY_SECONDS = Histogram(
    "rag_query_latency_seconds",
    "Per-stage query pipeline latency",
    labelnames=["stage"],  # retrieval | rerank | generation | total
)

CACHE_HITS_TOTAL = Counter("rag_cache_hits_total", "Query cache hits")
CACHE_MISSES_TOTAL = Counter("rag_cache_misses_total", "Query cache misses")

CHUNKS_RETRIEVED = Histogram(
    "rag_chunks_retrieved",
    "Number of chunks retrieved per query before rerank",
    buckets=(1, 2, 5, 10, 20, 50),
)

LLM_TOKENS_TOTAL = Counter(
    "rag_llm_tokens_total",
    "LLM tokens consumed",
    labelnames=["type"],  # prompt | completion
)

ERRORS_TOTAL = Counter(
    "rag_errors_total",
    "Errors raised while serving a query",
    labelnames=["stage"],
)

QUERIES_TOTAL = Counter("rag_queries_total", "Total queries served")
