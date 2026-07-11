from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from core.database import get_db
from api.schemas import HistoryResponse, HistoryItem, SourceChunk, QueryMetrics
from api.dependencies import require_api_key
from services.analytics import get_recent_queries, get_feedback_map
from services.retrieval import retrieval_service

router = APIRouter(prefix="/api/v1", tags=["history"], dependencies=[Depends(require_api_key)])


@router.get("/history", response_model=HistoryResponse)
async def history(limit: int = 30, db: Session = Depends(get_db)):
    """Recent queries with their sources reconstructed from Pinecone by id, so a
    history entry renders identically to a live answer without re-running the pipeline."""
    rows = get_recent_queries(db, limit=limit)
    feedback_map = get_feedback_map(db, [row.query_id for row in rows])

    items = []
    for row in rows:
        retrieved_ids = row.retrieved_ids or []
        scores = row.scores or []
        scores_by_id = dict(zip(retrieved_ids, scores))

        chunks = retrieval_service.fetch_chunks(retrieved_ids, scores_by_id)
        sources = [
            SourceChunk(
                chunk_id=c.chunk_id,
                text=c.text,
                score=c.score,
                source=c.metadata.get("source"),
                dataset_name=c.metadata.get("dataset_name"),
            )
            for c in chunks
        ]

        metrics = QueryMetrics(
            cache_hit=row.cache_hit,
            retrieval_ms=row.retrieval_ms,
            rerank_ms=row.rerank_ms,
            generation_ms=row.generation_ms,
            total_ms=row.total_ms,
            # The original candidate-pool size before rerank isn't persisted -- the
            # retrieved (post-rerank) chunk count is the closest honest approximation.
            candidates_retrieved=len(retrieved_ids),
            chunks_used=len(retrieved_ids),
            top_score=max(scores) if scores else None,
            llm_prompt_tokens=row.prompt_tokens,
            llm_completion_tokens=row.completion_tokens,
            estimated_cost_usd=row.estimated_cost_usd,
            provider=row.provider,
            model=row.model,
            embedding_model=row.embedding_model,
        )

        items.append(
            HistoryItem(
                query_id=str(row.query_id),
                query_text=row.query_text,
                answer=row.answer,
                sources=sources,
                metrics=metrics,
                created_at=row.created_at.isoformat(),
                feedback=feedback_map.get(str(row.query_id)),
            )
        )

    return HistoryResponse(items=items)
