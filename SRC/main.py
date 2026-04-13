import logging
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest
from starlette.requests import Request
from starlette.responses import Response

from config import get_settings
from logging_setup import ACCESS_LOGGER_NAME, setup_logging
from Engine.graph import build_teaching_graph
from Routes.Content import router as content_router
from Routes.Eval import router as eval_router
from Routes.Health import router as health_router
from Routes.Progress import router as progress_router
from Routes.Project import router as project_router
from Routes.Report import router as report_router
from Routes.Session import router as session_router

logger = logging.getLogger(__name__)
_access = logging.getLogger(ACCESS_LOGGER_NAME)


def _langgraph_checkpoint_pool_kwargs(settings):
    """Connection kwargs for AsyncConnectionPool (libpq TCP keepalives)."""
    from psycopg.rows import dict_row

    kw: dict = {
        "autocommit": True,
        "prepare_threshold": 0,
        "row_factory": dict_row,
    }
    if settings.langgraph_checkpoint_tcp_keepalive:
        kw["keepalives"] = 1
        kw["keepalives_idle"] = settings.langgraph_checkpoint_keepalives_idle
        kw["keepalives_interval"] = settings.langgraph_checkpoint_keepalives_interval
        kw["keepalives_count"] = settings.langgraph_checkpoint_keepalives_count
    return kw


@asynccontextmanager
async def lifespan(app: FastAPI):
    setup_logging()
    settings = get_settings()
    logger.info("Socratic Tutor API starting (log_level=%s)", settings.log_level)
    app.state.stage2_asset_store = {}
    app.state.checkpoint_pool = None
    if settings.langgraph_checkpoint_backend.lower() == "postgres":
        from psycopg_pool import AsyncConnectionPool
        from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver

        conn_kw = _langgraph_checkpoint_pool_kwargs(settings)
        pool_args: dict = {
            "conninfo": settings.postgres_checkpoint_conninfo,
            "kwargs": conn_kw,
            "open": True,
            "min_size": 1,
            "max_size": 10,
        }
        if settings.langgraph_checkpoint_pool_max_idle_seconds > 0:
            pool_args["max_idle"] = settings.langgraph_checkpoint_pool_max_idle_seconds
        pool = AsyncConnectionPool(**pool_args)
        logger.info(
            "LangGraph checkpoint pool: tcp_keepalive=%s keepalives_idle=%s interval=%s count=%s max_idle=%s",
            settings.langgraph_checkpoint_tcp_keepalive,
            conn_kw.get("keepalives_idle", "—"),
            conn_kw.get("keepalives_interval", "—"),
            conn_kw.get("keepalives_count", "—"),
            pool_args.get("max_idle", "default"),
        )
        checkpointer = AsyncPostgresSaver(pool)
        await checkpointer.setup()
        app.state.checkpoint_pool = pool
        app.state.teaching_checkpointer = checkpointer
    else:
        from langgraph.checkpoint.memory import MemorySaver

        app.state.teaching_checkpointer = MemorySaver()

    app.state.teaching_graph = build_teaching_graph(app.state.teaching_checkpointer)
    logger.info(
        "Per-request lines: terminal (-> / <-) and access.log in the API working directory "
        "(if the terminal stays quiet, tail access.log - traffic may be hitting another process on :8000)."
    )
    yield
    pool = getattr(app.state, "checkpoint_pool", None)
    if pool is not None:
        await pool.close()
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
    _access.info("-> %s %s", request.method, path)
    start = time.perf_counter()
    try:
        response = await call_next(request)
    except Exception:
        _access.exception("<- FAILED %s %s", request.method, path)
        raise
    elapsed_ms = (time.perf_counter() - start) * 1000
    _access.info(
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
app.include_router(report_router, prefix=api_prefix)
app.include_router(progress_router, prefix=api_prefix)
app.include_router(project_router, prefix=api_prefix)
app.include_router(eval_router, prefix=api_prefix)


@app.get("/metrics")
async def metrics():
    return Response(content=generate_latest(), media_type=CONTENT_TYPE_LATEST)


@app.get("/")
async def root():
    return {"service": "socratic-tutor", "docs": "/docs"}
