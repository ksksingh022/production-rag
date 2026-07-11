from fastapi import APIRouter
from api.routes.health import router as health_router
from api.routes.query import router as query_router
from api.routes.stats import router as stats_router
from api.routes.history import router as history_router

router = APIRouter()
router.include_router(health_router)
router.include_router(query_router)
router.include_router(stats_router)
router.include_router(history_router)
