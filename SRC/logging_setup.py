"""Configure process logging once (called from FastAPI lifespan).

Uvicorn configures the root logger before the app loads, so we must replace/merge
config explicitly or DEBUG logs from Pipelines/Stores/etc. never appear.
"""

import logging
import sys
from pathlib import Path
from typing import IO, Any

from config import get_settings


def _line_buffer_stdio() -> None:
    """Reduce IDE/Windows buffering so logs appear as requests happen."""
    for stream in (sys.stdout, sys.stderr):
        reconfigure = getattr(stream, "reconfigure", None)
        if callable(reconfigure):
            try:
                reconfigure(line_buffering=True)
            except (OSError, ValueError):
                pass


# Per-request `->` / `<-` lines: own handler at INFO so they still print when LOG_LEVEL=WARNING.
ACCESS_LOGGER_NAME = "socratic.access"


class FlushStreamHandler(logging.StreamHandler):
    """Always flush after each record (helps Windows + IDE terminals with --reload)."""

    def emit(self, record: logging.LogRecord) -> None:
        super().emit(record)
        try:
            stream: IO[Any] = self.stream
            stream.flush()
        except OSError:
            pass

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
    _line_buffer_stdio()
    s = get_settings()
    level_name = (s.log_level or "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)

    fmt = logging.Formatter(
        fmt="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    handler = FlushStreamHandler(sys.stderr)
    handler.setLevel(logging.DEBUG)
    handler.setFormatter(fmt)

    root = logging.getLogger()
    root.handlers.clear()
    root.setLevel(level)
    root.addHandler(handler)

    access = logging.getLogger(ACCESS_LOGGER_NAME)
    access.handlers.clear()
    access.setLevel(logging.INFO)
    # Match uvicorn.access (stdout). Some Windows / Cursor + --reload setups show stdout
    # more reliably for per-request lines than stderr.
    access_handler = FlushStreamHandler(sys.stdout)
    access_handler.setLevel(logging.INFO)
    access_handler.setFormatter(fmt)
    access.addHandler(access_handler)
    # Always mirror access lines to cwd/access.log (gitignored *.log) so you can
    # tail in another terminal when the IDE hides reload-child stdout/stderr.
    access_file = Path.cwd() / "access.log"
    file_handler = logging.FileHandler(access_file, encoding="utf-8")
    file_handler.setLevel(logging.INFO)
    file_handler.setFormatter(fmt)
    access.addHandler(file_handler)
    access.propagate = False

    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logging.getLogger(name).setLevel(level)

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
        "Logging ready: level=%s (also %s for per-request lines if the terminal is quiet)",
        level_name,
        access_file,
    )
