import uuid
from pydantic import BaseModel, Field, field_validator
from core.config import settings


class QueryRequest(BaseModel):
    query: str
    top_k: int | None = None
    filters: dict | None = None
    rerank: bool | None = None
    use_cache: bool = True
    provider: str | None = None
    model: str | None = None

    @field_validator("query")
    @classmethod
    def validate_query(cls, v: str) -> str:
        v = v.strip()
        if not v:
            raise ValueError("query must not be empty")
        if len(v) > settings.MAX_QUERY_LENGTH:
            raise ValueError(f"query exceeds max length of {settings.MAX_QUERY_LENGTH} characters")
        return v

    @field_validator("model")
    @classmethod
    def validate_model(cls, v: str | None) -> str | None:
        if v is not None and v not in settings.LLM_ALLOWED_MODELS:
            raise ValueError(f"model '{v}' is not in LLM_ALLOWED_MODELS")
        return v


class SourceChunk(BaseModel):
    chunk_id: str
    text: str
    score: float
    source: str | None = None
    dataset_name: str | None = None


class QueryMetrics(BaseModel):
    cache_hit: bool
    retrieval_ms: float
    rerank_ms: float
    generation_ms: float
    total_ms: float
    candidates_retrieved: int
    chunks_used: int
    top_score: float | None = None
    llm_prompt_tokens: int | None = None
    llm_completion_tokens: int | None = None
    estimated_cost_usd: float | None = None
    provider: str
    model: str
    embedding_model: str


class QueryResponse(BaseModel):
    query_id: str
    answer: str
    sources: list[SourceChunk]
    metrics: QueryMetrics


class FeedbackRequest(BaseModel):
    query_id: str
    rating: int = Field(..., ge=-1, le=1)
    comment: str | None = None

    @field_validator("rating")
    @classmethod
    def validate_rating(cls, v: int) -> int:
        if v == 0:
            raise ValueError("rating must be +1 (positive) or -1 (negative)")
        return v


class LatencyPercentiles(BaseModel):
    p50: float
    p95: float
    p99: float


class FeedbackSummary(BaseModel):
    positive: int
    negative: int


class TopQuery(BaseModel):
    query: str
    count: int


class StatsResponse(BaseModel):
    total_queries: int
    queries_last_24h: int
    cache_hit_rate: float
    latency_ms: LatencyPercentiles
    avg_chunks_used: float
    error_rate: float
    total_tokens: int
    estimated_cost_usd_24h: float
    top_queries: list[TopQuery]
    feedback: FeedbackSummary


class TimelinePoint(BaseModel):
    created_at: str
    total_ms: float
    cache_hit: bool
    tokens: int


class TimelineResponse(BaseModel):
    points: list[TimelinePoint]


class HistoryItem(BaseModel):
    query_id: str
    query_text: str
    answer: str
    sources: list[SourceChunk]
    metrics: QueryMetrics
    created_at: str
    feedback: int | None = None


class HistoryResponse(BaseModel):
    items: list[HistoryItem]


class ErrorResponse(BaseModel):
    error: str
    detail: str | None = None
    request_id: str | None = None


def new_id() -> str:
    return str(uuid.uuid4())
