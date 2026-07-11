from datetime import datetime, timedelta, timezone
from sqlalchemy import func, select
from sqlalchemy.orm import Session
from models.query_log import QueryLog
from models.feedback import Feedback


def log_query(db: Session, **fields) -> QueryLog:
    entry = QueryLog(**fields)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def get_recent_queries(db: Session, limit: int = 30) -> list[QueryLog]:
    return list(
        db.execute(select(QueryLog).order_by(QueryLog.created_at.desc()).limit(limit)).scalars().all()
    )


def get_timeline(db: Session, limit: int = 200) -> list[dict]:
    """Chronological per-query datapoints for dashboard charts. Reads only scalar
    columns from Postgres (no Pinecone round-trips like /history), so it stays cheap
    enough to poll."""
    rows = db.execute(
        select(
            QueryLog.created_at,
            QueryLog.total_ms,
            QueryLog.cache_hit,
            QueryLog.prompt_tokens,
            QueryLog.completion_tokens,
        )
        .order_by(QueryLog.created_at.desc())
        .limit(limit)
    ).all()

    return [
        {
            "created_at": row.created_at.isoformat(),
            "total_ms": row.total_ms,
            "cache_hit": row.cache_hit,
            "tokens": (row.prompt_tokens or 0) + (row.completion_tokens or 0),
        }
        for row in reversed(rows)  # oldest first, ready to plot left-to-right
    ]


def get_feedback_for_query(db: Session, query_id) -> Feedback | None:
    return db.execute(select(Feedback).where(Feedback.query_id == query_id)).scalar_one_or_none()


def get_feedback_map(db: Session, query_ids: list) -> dict[str, int]:
    """Bulk-fetches existing ratings for a set of query_ids, keyed by str(query_id) --
    used to tell the client which history entries are already rated (and so locked)."""
    if not query_ids:
        return {}
    rows = db.execute(
        select(Feedback.query_id, Feedback.rating).where(Feedback.query_id.in_(query_ids))
    ).all()
    return {str(qid): rating for qid, rating in rows}


def save_feedback(db: Session, query_id, rating: int, comment: str | None) -> Feedback:
    entry = Feedback(query_id=query_id, rating=rating, comment=comment)
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def _percentile(sorted_values: list[float], pct: float) -> float:
    if not sorted_values:
        return 0.0
    idx = min(int(len(sorted_values) * pct), len(sorted_values) - 1)
    return sorted_values[idx]


def compute_stats(db: Session) -> dict:
    total_queries = db.scalar(select(func.count()).select_from(QueryLog)) or 0

    since_24h = datetime.now(timezone.utc) - timedelta(hours=24)
    queries_last_24h = db.scalar(
        select(func.count()).select_from(QueryLog).where(QueryLog.created_at >= since_24h)
    ) or 0

    cache_hits = db.scalar(select(func.count()).select_from(QueryLog).where(QueryLog.cache_hit.is_(True))) or 0
    cache_hit_rate = (cache_hits / total_queries) if total_queries else 0.0

    latencies = [row[0] for row in db.execute(select(QueryLog.total_ms)).all()]
    latencies.sort()

    avg_chunks_used = db.scalar(select(func.avg(func.json_array_length(QueryLog.retrieved_ids)))) or 0.0

    error_count = db.scalar(select(func.count()).select_from(QueryLog).where(QueryLog.error.is_not(None))) or 0
    error_rate = (error_count / total_queries) if total_queries else 0.0

    total_prompt_tokens = db.scalar(select(func.coalesce(func.sum(QueryLog.prompt_tokens), 0))) or 0
    total_completion_tokens = db.scalar(select(func.coalesce(func.sum(QueryLog.completion_tokens), 0))) or 0
    total_tokens = int(total_prompt_tokens) + int(total_completion_tokens)

    cost_24h = db.scalar(
        select(func.coalesce(func.sum(QueryLog.estimated_cost_usd), 0.0)).where(QueryLog.created_at >= since_24h)
    ) or 0.0

    top_queries_rows = db.execute(
        select(QueryLog.normalized_query, func.count().label("cnt"))
        .group_by(QueryLog.normalized_query)
        .order_by(func.count().desc())
        .limit(5)
    ).all()

    positive = db.scalar(select(func.count()).select_from(Feedback).where(Feedback.rating == 1)) or 0
    negative = db.scalar(select(func.count()).select_from(Feedback).where(Feedback.rating == -1)) or 0

    return {
        "total_queries": total_queries,
        "queries_last_24h": queries_last_24h,
        "cache_hit_rate": round(cache_hit_rate, 4),
        "latency_ms": {
            "p50": round(_percentile(latencies, 0.50), 1),
            "p95": round(_percentile(latencies, 0.95), 1),
            "p99": round(_percentile(latencies, 0.99), 1),
        },
        "avg_chunks_used": round(float(avg_chunks_used), 2),
        "error_rate": round(error_rate, 4),
        "total_tokens": total_tokens,
        "estimated_cost_usd_24h": round(float(cost_24h), 4),
        "top_queries": [{"query": q, "count": c} for q, c in top_queries_rows],
        "feedback": {"positive": positive, "negative": negative},
    }
