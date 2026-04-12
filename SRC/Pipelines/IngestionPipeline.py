from __future__ import annotations

import asyncio
import logging
import queue
import time
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from pathlib import Path

import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from Models.Content import Document
from Pipelines.KnowledgeGraphBuilder import KnowledgeGraphBuilder
from Stores.VectorStore import VectorStore

logger = logging.getLogger(__name__)


def _read_text(path: Path, source_type: str) -> str:
    if source_type == "pdf":
        from pypdf import PdfReader

        reader = PdfReader(str(path))
        parts: list[str] = []
        for page in reader.pages:
            parts.append(page.extract_text() or "")
        return "\n".join(parts)
    return path.read_text(encoding="utf-8", errors="replace")


class IngestionPipeline:
    def __init__(self, db: AsyncSession, upload_dir: Path | None = None) -> None:
        self._db = db
        self._settings = get_settings()
        self._upload_dir = upload_dir or Path(__file__).resolve().parent.parent / "uploads"
        self._upload_dir.mkdir(parents=True, exist_ok=True)
        self._vector = VectorStore()

    async def _check_ollama(self) -> None:
        url = f"{self._settings.ollama_base_url}/api/tags"
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                r = await client.get(url)
                r.raise_for_status()
        except Exception as e:
            raise RuntimeError(
                f"Cannot reach Ollama at {self._settings.ollama_base_url}: {e}"
            ) from e

    async def _check_chroma(self) -> None:
        try:
            import chromadb

            chroma = chromadb.HttpClient(
                host=self._settings.chroma_host, port=self._settings.chroma_port
            )
            chroma.heartbeat()
        except Exception as e:
            raise RuntimeError(
                f"Cannot reach ChromaDB at {self._settings.chroma_host}:{self._settings.chroma_port}: {e}"
            ) from e

    async def ingest_document(self, document_id: uuid.UUID) -> Document:
        t_start = time.perf_counter()
        logger.info("Ingest: start document_id=%s", document_id)

        logger.info("Ingest: pre-flight — checking Ollama and ChromaDB connectivity")
        await self._check_ollama()
        await self._check_chroma()
        logger.info("Ingest: pre-flight passed")
        doc = (
            await self._db.execute(select(Document).where(Document.id == document_id))
        ).scalar_one_or_none()
        if doc is None:
            raise ValueError(f"document not found: {document_id}")
        if not doc.storage_path:
            raise ValueError("document has no storage_path")
        path = Path(doc.storage_path)
        if not path.is_file():
            raise ValueError(f"upload file missing on disk: {path}")
        logger.info("Ingest: reading file path=%s type=%s", path, doc.source_type)
        text = _read_text(path, doc.source_type)
        logger.info("Ingest: extracted %s chars (%.0f KB)", len(text), len(text) / 1024)

        t_kg = time.perf_counter()
        builder = KnowledgeGraphBuilder(self._db)
        concepts, _ = await builder.build_from_text(doc.id, text)
        primary = concepts[0]
        logger.info("Ingest: KG built in %.1fs", time.perf_counter() - t_kg)

        def _build() -> int:
            return self._vector.build_index_from_text(
                document_id, text, primary.id, doc.title
            )

        logger.info(
            "Ingest: building vector index concept_id=%s (embeddings via configured backend)",
            primary.id,
        )
        t_embed = time.perf_counter()
        try:
            n_chunks = await asyncio.to_thread(_build)
        except Exception as e:
            logger.exception("Ingest: vector index failed for document_id=%s", document_id)
            raise RuntimeError(
                "Vector indexing failed. Ensure Chroma is running (e.g. Docker dev compose) "
                f"and the embedding backend can reach Ollama/API. Underlying error: {e}"
            ) from e
        logger.info("Ingest: embeddings built in %.1fs", time.perf_counter() - t_embed)

        doc.chunk_count = n_chunks
        doc.ingested_at = datetime.now(timezone.utc)
        await self._db.refresh(doc)

        total = time.perf_counter() - t_start
        logger.info(
            "========== Ingest COMPLETE: doc=%s chunks=%s total=%.1fs ==========",
            document_id, n_chunks, total,
        )
        return doc

    # ------------------------------------------------------------------
    # Streaming variant — yields progress dicts for SSE
    # ------------------------------------------------------------------

    async def ingest_document_stream(
        self, document_id: uuid.UUID
    ) -> AsyncIterator[dict]:
        t_start = time.perf_counter()
        logger.info("Ingest(stream): start document_id=%s", document_id)

        yield {"event": "progress", "step": "preflight", "detail": "Checking services...", "pct": 0}
        await self._check_ollama()
        await self._check_chroma()

        doc = (
            await self._db.execute(select(Document).where(Document.id == document_id))
        ).scalar_one_or_none()
        if doc is None:
            raise ValueError(f"document not found: {document_id}")
        if not doc.storage_path:
            raise ValueError("document has no storage_path")
        path = Path(doc.storage_path)
        if not path.is_file():
            raise ValueError(f"upload file missing on disk: {path}")

        yield {"event": "progress", "step": "extracting", "detail": f"Reading {doc.source_type}...", "pct": 5}
        text = _read_text(path, doc.source_type)
        chars = len(text)
        logger.info("Ingest(stream): extracted %s chars", chars)

        yield {"event": "progress", "step": "kg", "detail": f"Building concept graph ({chars // 1024} KB)...", "pct": 10}
        builder = KnowledgeGraphBuilder(self._db)
        concepts, _ = await builder.build_from_text(doc.id, text)
        primary = concepts[0]
        yield {"event": "progress", "step": "kg_done", "detail": f"{len(concepts)} concepts found", "pct": 30}

        progress_q: queue.Queue[tuple[int, int, int]] = queue.Queue()

        def _on_batch(batch_num: int, total_batches: int, embedded: int) -> None:
            progress_q.put((batch_num, total_batches, embedded))

        def _build() -> int:
            return self._vector.build_index_from_text(
                document_id, text, primary.id, doc.title, progress_callback=_on_batch,
            )

        yield {"event": "progress", "step": "embedding", "detail": "Starting embeddings...", "pct": 30}

        loop = asyncio.get_event_loop()
        fut = loop.run_in_executor(None, _build)

        while not fut.done():
            await asyncio.sleep(0.5)
            while not progress_q.empty():
                batch_num, total_batches, embedded = progress_q.get_nowait()
                pct = 30 + int(70 * batch_num / max(total_batches, 1))
                yield {
                    "event": "progress",
                    "step": "embedding",
                    "detail": f"Batch {batch_num}/{total_batches}",
                    "pct": min(pct, 99),
                    "batch": batch_num,
                    "total_batches": total_batches,
                }

        try:
            n_chunks = fut.result()
        except Exception as e:
            logger.exception("Ingest(stream): vector index failed doc=%s", document_id)
            raise RuntimeError(
                f"Vector indexing failed: {e}"
            ) from e

        while not progress_q.empty():
            batch_num, total_batches, embedded = progress_q.get_nowait()
            pct = 30 + int(70 * batch_num / max(total_batches, 1))
            yield {"event": "progress", "step": "embedding", "detail": f"Batch {batch_num}/{total_batches}", "pct": min(pct, 99)}

        doc.chunk_count = n_chunks
        doc.ingested_at = datetime.now(timezone.utc)
        await self._db.refresh(doc)

        total_s = time.perf_counter() - t_start
        logger.info("========== Ingest(stream) COMPLETE: doc=%s chunks=%s total=%.1fs ==========", document_id, n_chunks, total_s)

        yield {
            "event": "done",
            "pct": 100,
            "document": {
                "id": str(doc.id),
                "title": doc.title,
                "source_type": doc.source_type,
                "chunk_count": doc.chunk_count,
                "ingested_at": doc.ingested_at.isoformat(),
            },
        }
