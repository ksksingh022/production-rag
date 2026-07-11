from fastapi import APIRouter
from core import vector_manager, cache_manager, get_logger
from core.database import engine
from sqlalchemy import text

logger = get_logger("health")
router = APIRouter(tags=["health"])


@router.get("/health/live")
async def liveness():
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness():
    checks = {}

    try:
        vector_manager.get_index().describe_index_stats()
        checks["pinecone"] = "ok"
    except Exception as e:
        checks["pinecone"] = f"error: {e}"

    try:
        cache_manager.get_client().ping()
        checks["valkey"] = "ok"
    except Exception as e:
        checks["valkey"] = f"error: {e}"

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["postgres"] = "ok"
    except Exception as e:
        checks["postgres"] = f"error: {e}"

    healthy = all(v == "ok" for v in checks.values())
    return {"status": "ready" if healthy else "not_ready", "checks": checks}
