import time
import uuid
from contextlib import asynccontextmanager

import structlog
import structlog.contextvars
from fastapi import FastAPI, Request
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from sqlalchemy import text

from jobplatform.auth.router import router as auth_router
from jobplatform.profiles.router import router as profiles_router
from jobplatform.preferences.router import router as preferences_router
from jobplatform.resumes.router import router as resumes_router
from jobplatform.jobs.router import router as jobs_router
from jobplatform.workers.router import router as workers_router
from jobplatform.log_config import configure_logging
from jobplatform.database import AsyncSessionLocal
from jobplatform.rate_limiting import limiter

configure_logging()
logger = structlog.get_logger()


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("startup")
    yield
    logger.info("shutdown")


app = FastAPI(title="Job Platform API", version="0.1.0", lifespan=lifespan)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.include_router(auth_router)
app.include_router(profiles_router)
app.include_router(preferences_router)
app.include_router(resumes_router)
app.include_router(jobs_router)
app.include_router(workers_router)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(request_id=str(uuid.uuid4()))
    start = time.perf_counter()
    response = await call_next(request)
    duration_ms = round((time.perf_counter() - start) * 1000)
    logger.info(
        "request",
        method=request.method,
        path=request.url.path,
        status=response.status_code,
        duration_ms=duration_ms,
    )
    return response


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready():
    async with AsyncSessionLocal() as session:
        await session.execute(text("SELECT 1"))
    return {"status": "ready"}
