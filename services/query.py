import time
import uuid
from sqlalchemy.orm import Session
from core.config import settings
from core.reranker import reranker
from core.embeddings import hf_embedding_client
from core.metrics import (
    QUERY_LATENCY_SECONDS,
    CACHE_HITS_TOTAL,
    CACHE_MISSES_TOTAL,
    CHUNKS_RETRIEVED,
    LLM_TOKENS_TOTAL,
    ERRORS_TOTAL,
    QUERIES_TOTAL,
)
from core import get_logger
from services.retrieval import retrieval_service
from services.generation import generation_service
from services.cache_service import query_cache_service, _normalize_query
from services.analytics import log_query

logger = get_logger("query_service")


class QueryService:
    """Orchestrates the full query lifecycle: cache -> retrieve -> rerank -> generate ->
    persist -> cache. Central place where per-stage timings/metrics are recorded."""

    def answer(
        self,
        db: Session,
        query: str,
        top_k: int | None = None,
        filters: dict | None = None,
        rerank: bool | None = None,
        use_cache: bool = True,
        provider: str | None = None,
        model: str | None = None,
    ) -> dict:
        QUERIES_TOTAL.inc()
        start_total = time.time()

        top_k = top_k or settings.TOP_K
        rerank_enabled = settings.RERANK_ENABLED if rerank is None else rerank
        resolved_provider, resolved_model = generation_service.resolve(provider, model)

        if use_cache:
            cached = query_cache_service.get(query, filters, top_k, resolved_provider, resolved_model)
            if cached:
                CACHE_HITS_TOTAL.inc()
                return self._replay_from_cache(db, query, cached, start_total)
        CACHE_MISSES_TOTAL.inc()

        # --- Retrieval ---
        t0 = time.time()
        try:
            candidates = retrieval_service.retrieve(query, filters=filters)
        except Exception as e:
            ERRORS_TOTAL.labels(stage="retrieval").inc()
            logger.error(f"Retrieval failed: {e}")
            raise
        retrieval_ms = (time.time() - t0) * 1000
        QUERY_LATENCY_SECONDS.labels(stage="retrieval").observe(retrieval_ms / 1000)
        CHUNKS_RETRIEVED.observe(len(candidates))

        # --- Rerank ---
        t0 = time.time()
        if rerank_enabled and candidates:
            try:
                top_chunks = reranker.rerank(query, candidates, top_k=top_k)
            except Exception as e:
                ERRORS_TOTAL.labels(stage="rerank").inc()
                logger.warning(f"Rerank failed, falling back to retrieval order: {e}")
                top_chunks = candidates[:top_k]
        else:
            top_chunks = candidates[:top_k]
        rerank_ms = (time.time() - t0) * 1000
        QUERY_LATENCY_SECONDS.labels(stage="rerank").observe(rerank_ms / 1000)

        # --- Generation ---
        t0 = time.time()
        try:
            result = generation_service.generate(
                query, top_chunks, provider=resolved_provider, model=resolved_model
            )
        except Exception as e:
            ERRORS_TOTAL.labels(stage="generation").inc()
            logger.error(f"Generation failed: {e}")
            raise
        generation_ms = (time.time() - t0) * 1000
        QUERY_LATENCY_SECONDS.labels(stage="generation").observe(generation_ms / 1000)

        LLM_TOKENS_TOTAL.labels(type="prompt").inc(result.prompt_tokens)
        LLM_TOKENS_TOTAL.labels(type="completion").inc(result.completion_tokens)

        total_ms = (time.time() - start_total) * 1000
        QUERY_LATENCY_SECONDS.labels(stage="total").observe(total_ms / 1000)

        query_id = uuid.uuid4()
        embedding_model = hf_embedding_client.model_name

        response = {
            "query_id": str(query_id),
            "answer": result.text,
            "sources": [
                {
                    "chunk_id": c.chunk_id,
                    "text": c.text,
                    "score": c.score,
                    "source": c.metadata.get("source"),
                    "dataset_name": c.metadata.get("dataset_name"),
                }
                for c in top_chunks
            ],
            "metrics": {
                "cache_hit": False,
                "retrieval_ms": round(retrieval_ms, 1),
                "rerank_ms": round(rerank_ms, 1),
                "generation_ms": round(generation_ms, 1),
                "total_ms": round(total_ms, 1),
                "candidates_retrieved": len(candidates),
                "chunks_used": len(top_chunks),
                "top_score": top_chunks[0].score if top_chunks else None,
                "llm_prompt_tokens": result.prompt_tokens,
                "llm_completion_tokens": result.completion_tokens,
                "estimated_cost_usd": result.estimated_cost_usd,
                "provider": result.provider,
                "model": result.model,
                "embedding_model": embedding_model,
            },
        }

        try:
            log_query(
                db,
                query_id=query_id,
                query_text=query,
                normalized_query=_normalize_query(query),
                retrieved_ids=[c.chunk_id for c in top_chunks],
                scores=[c.score for c in top_chunks],
                answer=result.text,
                retrieval_ms=retrieval_ms,
                rerank_ms=rerank_ms,
                generation_ms=generation_ms,
                total_ms=total_ms,
                prompt_tokens=result.prompt_tokens,
                completion_tokens=result.completion_tokens,
                estimated_cost_usd=result.estimated_cost_usd,
                cache_hit=False,
                provider=result.provider,
                model=result.model,
                embedding_model=embedding_model,
            )
        except Exception as e:
            logger.warning(f"Failed to persist query log: {e}")

        if use_cache:
            try:
                query_cache_service.set(query, filters, top_k, result.provider, result.model, response)
            except Exception as e:
                logger.warning(f"Failed to write query cache: {e}")

        return response

    def _replay_from_cache(self, db: Session, query: str, cached: dict, start_total: float) -> dict:
        """Serves a cached answer under a fresh query_id, logged with its own (near-zero)
        latency and cache_hit=True -- so repeated questions show up as distinct, instant
        entries in history/stats instead of silently vanishing from the analytics."""
        query_id = uuid.uuid4()
        total_ms = (time.time() - start_total) * 1000
        # A cache hit makes no new LLM call, so its true incremental cost is $0 --
        # overriding rather than replaying the original generation's cost figure.
        metrics = {
            **cached["metrics"],
            "cache_hit": True,
            # None of these stages actually ran this time -- zero them out rather than
            # showing the stale timings from whichever request first populated the cache.
            "retrieval_ms": 0.0,
            "rerank_ms": 0.0,
            "generation_ms": 0.0,
            "total_ms": round(total_ms, 1),
            "estimated_cost_usd": 0.0,
        }
        response = {"query_id": str(query_id), "answer": cached["answer"], "sources": cached["sources"], "metrics": metrics}

        try:
            log_query(
                db,
                query_id=query_id,
                query_text=query,
                normalized_query=_normalize_query(query),
                retrieved_ids=[s["chunk_id"] for s in cached["sources"]],
                scores=[s["score"] for s in cached["sources"]],
                answer=cached["answer"],
                retrieval_ms=0.0,
                rerank_ms=0.0,
                generation_ms=0.0,
                total_ms=total_ms,
                # Zero here (unlike the response metrics, which still show the original
                # answer's token counts as informational) -- this specific request made
                # no new LLM call, so it shouldn't inflate the dashboard's total_tokens sum.
                prompt_tokens=0,
                completion_tokens=0,
                estimated_cost_usd=0.0,
                cache_hit=True,
                provider=metrics["provider"],
                model=metrics["model"],
                embedding_model=metrics["embedding_model"],
            )
        except Exception as e:
            logger.warning(f"Failed to persist cached query log: {e}")

        return response


query_service = QueryService()
