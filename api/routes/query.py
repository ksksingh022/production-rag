import json
import time
import uuid
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session
from sqlalchemy.exc import IntegrityError

from core.database import get_db, SessionLocal
from core.config import settings
from core.reranker import reranker
from core.embeddings import hf_embedding_client
from core.llm.registry import estimate_cost_usd
from core import get_logger
from api.schemas import QueryRequest, QueryResponse, FeedbackRequest
from api.dependencies import require_api_key
from api.rate_limit import limiter
from services.retrieval import retrieval_service
from services.generation import generation_service
from services.query import query_service
from services.cache_service import query_cache_service, _normalize_query
from services.analytics import log_query, save_feedback, get_feedback_for_query

logger = get_logger("query_routes")
router = APIRouter(prefix="/api/v1", tags=["query"], dependencies=[Depends(require_api_key)])


@router.post("/query", response_model=QueryResponse)
@limiter.limit(f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
async def query(request: Request, payload: QueryRequest, db: Session = Depends(get_db)):
    try:
        return query_service.answer(
            db,
            query=payload.query,
            top_k=payload.top_k,
            filters=payload.filters,
            rerank=payload.rerank,
            use_cache=payload.use_cache,
            provider=payload.provider,
            model=payload.model,
        )
    except Exception as e:
        logger.error(f"Query failed: {e}")
        raise HTTPException(status_code=502, detail=f"Query pipeline error: {e}")


@router.post("/query/stream")
@limiter.limit(f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
async def query_stream(request: Request, payload: QueryRequest):
    """SSE stream of answer tokens, followed by a final event with sources/metrics.
    Shares the same Valkey cache as POST /query -- a cache hit replays the stored
    answer as a single delta instead of re-running retrieval/rerank/generation.

    No DB session is injected at the route level -- a stream can run for a while
    and the client can disconnect mid-generation, which would otherwise hold a
    request-scoped session (and its pool connection) open indefinitely since
    its cleanup never runs on an abandoned generator. Each generator opens its
    own short-lived session only at the point it actually writes the query log.
    """
    start_total = time.time()
    top_k = payload.top_k or settings.TOP_K
    rerank_enabled = settings.RERANK_ENABLED if payload.rerank is None else payload.rerank
    provider, model = generation_service.resolve(payload.provider, payload.model)

    if payload.use_cache:
        cached = query_cache_service.get(payload.query, payload.filters, top_k, provider, model)
        if cached:
            def cached_stream():
                yield f"data: {json.dumps({'delta': cached['answer']})}\n\n"

                query_id = uuid.uuid4()
                total_ms = (time.time() - start_total) * 1000
                # Real latency/cost/tokens for THIS request (near-zero, since nothing
                # actually ran) -- llm_prompt_tokens/completion_tokens stay informational
                # (the original answer's counts), matching the non-streaming cache path.
                metrics = {
                    **cached["metrics"],
                    "cache_hit": True,
                    "retrieval_ms": 0.0,
                    "rerank_ms": 0.0,
                    "generation_ms": 0.0,
                    "total_ms": round(total_ms, 1),
                    "estimated_cost_usd": 0.0,
                }
                yield f"data: {json.dumps({'done': True, 'query_id': str(query_id), 'sources': cached['sources'], 'metrics': metrics})}\n\n"

                try:
                    with SessionLocal() as db:
                        log_query(
                            db, query_id=query_id, query_text=payload.query,
                            normalized_query=_normalize_query(payload.query),
                            retrieved_ids=[s["chunk_id"] for s in cached["sources"]],
                            scores=[s["score"] for s in cached["sources"]],
                            answer=cached["answer"], retrieval_ms=0.0, rerank_ms=0.0, generation_ms=0.0,
                            total_ms=total_ms, prompt_tokens=0, completion_tokens=0, estimated_cost_usd=0.0,
                            cache_hit=True, provider=provider, model=model,
                            embedding_model=hf_embedding_client.model_name,
                        )
                except Exception as e:
                    logger.warning(f"Failed to persist cached streamed query log: {e}")

            return StreamingResponse(cached_stream(), media_type="text/event-stream")

    t0 = time.time()
    candidates = retrieval_service.retrieve(payload.query, filters=payload.filters)
    retrieval_ms = (time.time() - t0) * 1000

    t0 = time.time()
    if rerank_enabled and candidates:
        top_chunks = reranker.rerank(payload.query, candidates, top_k=top_k)
    else:
        top_chunks = candidates[:top_k]
    rerank_ms = (time.time() - t0) * 1000

    def event_stream():
        full_text = ""
        prompt_tokens: int | None = None
        completion_tokens: int | None = None
        gen_start = time.time()
        try:
            for chunk in generation_service.stream(payload.query, top_chunks, provider=provider, model=model):
                if chunk.delta:
                    full_text += chunk.delta
                    yield f"data: {json.dumps({'delta': chunk.delta})}\n\n"
                if chunk.usage:
                    prompt_tokens = chunk.usage.get("prompt_tokens")
                    completion_tokens = chunk.usage.get("completion_tokens")
        except Exception as e:
            logger.error(f"Streaming generation failed: {e}")
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
            return
        generation_ms = (time.time() - gen_start) * 1000
        total_ms = (time.time() - start_total) * 1000

        cost = (
            estimate_cost_usd(model, prompt_tokens, completion_tokens)
            if prompt_tokens is not None and completion_tokens is not None
            else None
        )

        sources = [
            {
                "chunk_id": c.chunk_id, "text": c.text, "score": c.score,
                "source": c.metadata.get("source"), "dataset_name": c.metadata.get("dataset_name"),
            }
            for c in top_chunks
        ]
        query_id = uuid.uuid4()
        metrics = {
            "cache_hit": False,
            "retrieval_ms": round(retrieval_ms, 1),
            "rerank_ms": round(rerank_ms, 1),
            "generation_ms": round(generation_ms, 1),
            "total_ms": round(total_ms, 1),
            "candidates_retrieved": len(candidates),
            "chunks_used": len(top_chunks),
            "top_score": top_chunks[0].score if top_chunks else None,
            "llm_prompt_tokens": prompt_tokens,
            "llm_completion_tokens": completion_tokens,
            "estimated_cost_usd": cost,
            "provider": provider,
            "model": model,
            "embedding_model": hf_embedding_client.model_name,
        }
        yield f"data: {json.dumps({'done': True, 'query_id': str(query_id), 'sources': sources, 'metrics': metrics})}\n\n"

        try:
            with SessionLocal() as db:
                log_query(
                    db, query_id=query_id, query_text=payload.query,
                    normalized_query=_normalize_query(payload.query),
                    retrieved_ids=[c.chunk_id for c in top_chunks], scores=[c.score for c in top_chunks],
                    answer=full_text, retrieval_ms=retrieval_ms, rerank_ms=rerank_ms,
                    generation_ms=generation_ms, total_ms=total_ms,
                    prompt_tokens=prompt_tokens, completion_tokens=completion_tokens,
                    estimated_cost_usd=cost, cache_hit=False,
                    provider=provider, model=model, embedding_model=hf_embedding_client.model_name,
                )
        except Exception as e:
            logger.warning(f"Failed to persist streamed query log: {e}")

        if payload.use_cache:
            try:
                query_cache_service.set(
                    payload.query, payload.filters, top_k, provider, model,
                    {"query_id": str(query_id), "answer": full_text, "sources": sources, "metrics": metrics},
                )
            except Exception as e:
                logger.warning(f"Failed to write streamed query cache: {e}")

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@router.post("/feedback")
async def feedback(payload: FeedbackRequest, db: Session = Depends(get_db)):
    try:
        query_uuid = uuid.UUID(payload.query_id)
    except ValueError:
        raise HTTPException(status_code=400, detail="query_id must be a valid UUID")

    # A query is rateable once -- reject a second vote server-side too, not just via
    # the UI locking the buttons (a stale page reload or a second tab must not be able
    # to double-submit and skew the aggregate feedback counts).
    existing = get_feedback_for_query(db, query_uuid)
    if existing is not None:
        raise HTTPException(
            status_code=409,
            detail=f"Feedback already submitted for this query (rating={existing.rating})",
        )

    try:
        save_feedback(db, query_uuid, payload.rating, payload.comment)
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=404, detail="query_id not found")
    return {"status": "ok"}
