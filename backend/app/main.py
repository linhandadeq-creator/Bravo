import time
from collections import defaultdict, deque

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from app.api.router import api_router
from app.core.config import settings
from app.services.uploads import UploadTooLargeError

app = FastAPI(
    title=settings.APP_NAME,
    version="0.1.0",
    description="Scientific computing and simulation platform for personalized neoantigen analysis.",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in settings.BACKEND_CORS_ORIGINS.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

_OPEN_PATHS = {"/api/health"}


class AuthMiddleware(BaseHTTPMiddleware):
    """Optional token gate. Disabled when ``settings.API_TOKEN`` is empty."""

    async def dispatch(self, request: Request, call_next):  # noqa: ANN001
        token = (settings.API_TOKEN or "").strip()
        path = request.url.path
        if token and path.startswith(settings.API_PREFIX) and path not in _OPEN_PATHS:
            header = request.headers.get("authorization", "")
            provided = ""
            if header.lower().startswith("bearer "):
                provided = header[7:].strip()
            if not provided:
                provided = request.headers.get("x-api-key", "").strip()
            if provided != token:
                return JSONResponse(
                    status_code=401, content={"detail": "Unauthorized"}
                )
        return await call_next(request)


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Lightweight in-memory per-client rate limiter (0 = disabled)."""

    def __init__(self, app) -> None:  # noqa: ANN001
        super().__init__(app)
        self._hits: dict[str, deque] = defaultdict(deque)

    async def dispatch(self, request: Request, call_next):  # noqa: ANN001
        limit = int(getattr(settings, "RATE_LIMIT_PER_MINUTE", 0) or 0)
        if limit > 0 and request.url.path.startswith(settings.API_PREFIX):
            client = request.client.host if request.client else "unknown"
            now = time.time()
            window = self._hits[client]
            while window and now - window[0] > 60:
                window.popleft()
            if len(window) >= limit:
                return JSONResponse(
                    status_code=429,
                    content={"detail": "Rate limit exceeded. Try again later."},
                )
            window.append(now)
        return await call_next(request)


@app.exception_handler(UploadTooLargeError)
async def _upload_too_large(_request: Request, exc: UploadTooLargeError) -> JSONResponse:
    return JSONResponse(status_code=413, content={"detail": str(exc)})


app.add_middleware(RateLimitMiddleware)
app.add_middleware(AuthMiddleware)


app.include_router(api_router, prefix=settings.API_PREFIX)


@app.get("/", tags=["root"])
def root() -> dict[str, str]:
    return {"service": settings.APP_NAME, "docs": "/docs"}
