import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Integer, Float, Boolean, DateTime, JSON
from sqlalchemy.dialects.postgresql import UUID
from core.database import Base


class QueryLog(Base):
    __tablename__ = "query_logs"

    query_id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    query_text = Column(String, nullable=False)
    normalized_query = Column(String, nullable=False)
    retrieved_ids = Column(JSON, nullable=False, default=list)
    scores = Column(JSON, nullable=False, default=list)
    answer = Column(String, nullable=False)

    retrieval_ms = Column(Float, nullable=False)
    rerank_ms = Column(Float, nullable=False)
    generation_ms = Column(Float, nullable=False)
    total_ms = Column(Float, nullable=False)

    prompt_tokens = Column(Integer, nullable=True)
    completion_tokens = Column(Integer, nullable=True)
    estimated_cost_usd = Column(Float, nullable=True)
    cache_hit = Column(Boolean, nullable=False, default=False)

    provider = Column(String, nullable=False)
    model = Column(String, nullable=False)
    embedding_model = Column(String, nullable=False)

    error = Column(String, nullable=True)

    created_at = Column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), index=True)
