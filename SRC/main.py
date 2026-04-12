import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.requests import Request
from starlette.responses import Response

from config import get_settings
from logging_setup import setup_logging
from Routes.Content import router as content_router
from Routes.Eval import router as eval_router
from Routes.Health import router as health_router
from Routes.Progress import router as progress_router
from Routes.Project import router as project_router
from Routes.Session import router as session_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    logger.info("Socratic Tutor API starting (log_level=%s)", get_settings().log_level)
    logger.info(
        "Tip: each HTTP request prints '->' and '<-' in this terminal; try GET /api/v1/health/live or open /docs"
    )
    yield
    logger.info("Socratic Tutor API shutdown")


settings = get_settings()
app = FastAPI(title="Socratic Tutor API", version="0.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def request_logging_middleware(request: Request, call_next):
    path = request.url.path
    logger.info("-> %s %s", request.method, path)
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        logger.exception("<- FAILED %s %s", request.method, path)
        raise
    elapsed_ms = (time.perf_counter() - start) * 1000
    logger.info(
        "<- %s %s %s %.1fms",
        request.method,
        path,
        response.status_code,
        elapsed_ms,
    )
    return response


api_prefix = "/api/v1"
app.include_router(health_router, prefix=api_prefix)
app.include_router(content_router, prefix=api_prefix)
app.include_router(session_router, prefix=api_prefix)
app.include_router(progress_router, prefix=api_prefix)
app.include_router(project_router, prefix=api_prefix)
app.include_router(eval_router, prefix=api_prefix)


@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/")
async def root():
    return {"service": "socratic-tutor", "docs": "/docs"}
