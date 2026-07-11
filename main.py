from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from api.routes import router as api_router
from api.middleware import RequestContextMiddleware, unhandled_exception_handler
from api.rate_limit import limiter
from prometheus_fastapi_instrumentator import Instrumentator
from core.config import settings
from core.database import Base, engine
import models  # noqa: F401 -- registers QueryLog/Feedback on Base.metadata before create_all

# Query-side tables (query_logs, feedback) -- created here for now; move to Alembic
# migrations before this ships to a real production environment.
Base.metadata.create_all(bind=engine)

app = FastAPI(title=settings.APP_NAME)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, lambda request, exc: JSONResponse(
    status_code=429, content={"error": "rate_limited", "detail": str(exc.detail)}
))
app.add_middleware(SlowAPIMiddleware)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestContextMiddleware)
app.add_exception_handler(Exception, unhandled_exception_handler)

app.include_router(api_router)

Instrumentator().instrument(app).expose(app, endpoint="/metrics")

@app.get("/")
def root():
    return {"message": "Welcome to the Main App"}
