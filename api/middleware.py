import time
import uuid
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from core import get_logger

logger = get_logger("api_middleware")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Tags every request with a correlation ID (propagated to logs and the response
    header) and logs method/path/status/duration for basic request-level observability."""

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        start = time.time()

        try:
            response = await call_next(request)
        except Exception:
            duration_ms = (time.time() - start) * 1000
            logger.exception(
                f"request_id={request_id} method={request.method} path={request.url.path} "
                f"status=500 duration_ms={duration_ms:.1f} (unhandled exception)"
            )
            raise

        duration_ms = (time.time() - start) * 1000
        response.headers["X-Request-ID"] = request_id
        logger.info(
            f"request_id={request_id} method={request.method} path={request.url.path} "
            f"status={response.status_code} duration_ms={duration_ms:.1f}"
        )
        return response


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = getattr(request.state, "request_id", None)
    logger.error(f"request_id={request_id} unhandled error: {exc}")
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "detail": str(exc), "request_id": request_id},
    )
