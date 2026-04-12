"""Configure process logging once (called from FastAPI lifespan).

Uvicorn configures the root logger before the app loads, so we must replace/merge
config explicitly or DEBUG logs from Pipelines/Stores/etc. never appear.
"""

import logging
import sys

from config import get_settings

# Loggers under these prefixes get the configured level (so DEBUG shows ingest/engine noise).
_APP_PREFIXES = (
    "main",
    "Routes",
    "Controllers",
    "Pipelines",
    "Stores",
    "Engine",
    "Models",
    "Utils",
    "database",
    "deps",
    "logging_setup",
)


def setup_logging() -> None:
    s = get_settings()
    level_name = (s.log_level or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    handler = logging.StreamHandler(sys.stderr)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(fmt)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    root.addHandler(handler)

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        lg = logging.getLogger(name)
        lg.setLevel(level)
        lg.propagate = True

    for prefix in _APP_PREFIXES:
        logging.getLogger(prefix).setLevel(level)

    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    if level > logging.DEBUG:
        logging.getLogger("chromadb").setLevel(logging.WARNING)
    else:
        logging.getLogger("chromadb").setLevel(logging.INFO)

    if s.sqlalchemy_echo:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO)
    else:
        logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    logging.getLogger(__name__).info(
        "Logging ready: level=%s (HTTP requests log as -> / <- on each call)",
        level_name,
    )
