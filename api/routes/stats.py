from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from core.database import get_db
from api.schemas import StatsResponse, TimelineResponse
from api.dependencies import require_api_key
from services.analytics import compute_stats, get_timeline

router = APIRouter(prefix="/api/v1", tags=["stats"], dependencies=[Depends(require_api_key)])


@router.get("/stats", response_model=StatsResponse)
async def stats(db: Session = Depends(get_db)):
    return compute_stats(db)


@router.get("/stats/timeline", response_model=TimelineResponse)
async def stats_timeline(limit: int = 200, db: Session = Depends(get_db)):
    return {"points": get_timeline(db, limit=limit)}
