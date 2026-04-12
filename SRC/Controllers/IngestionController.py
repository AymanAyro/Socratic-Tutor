from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncIterator
from datetime import datetime, timezone
from pathlib import Path

from fastapi import HTTPException, UploadFile
from sqlalchemy import or_, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from Models.Content import Concept, ConceptEdge, Document
from Models.Schemas import ConceptEdgeOut, ConceptGraphResponse, ConceptOut, DocumentOut, UploadResponse
from Pipelines.IngestionPipeline import IngestionPipeline
from Stores.VectorStore import VectorStore
from Utils.StreamingHandler import sse_event

logger = logging.getLogger(__name__)


class IngestionController:
    def __init__(self, upload_dir: Path | None = None) -> None:
        self._upload_dir = upload_dir or Path(__file__).resolve().parent.parent / "uploads"
        self._upload_dir.mkdir(parents=True, exist_ok=True)
        self._vector = VectorStore()

    async def upload(self, db: AsyncSession, file: UploadFile, project_id: uuid.UUID | None = None) -> UploadResponse:
        raw_name = file.filename or "upload"
        suffix = Path(raw_name).suffix.lower()
        if suffix == ".pdf":
            source_type = "pdf"
        elif suffix in (".md", ".markdown"):
            source_type = "md"
        else:
            source_type = "txt"
        doc_id = uuid.uuid4()
        safe_name = f"{doc_id}_{raw_name}"
        path = self._upload_dir / safe_name
        content = await file.read()
        path.write_bytes(content)
        now = datetime.now(timezone.utc)
        kwargs: dict = dict(
            id=doc_id,
            title=raw_name[:512],
            source_type=source_type,
            chunk_count=0,
            ingested_at=now,
            storage_path=str(path.resolve()),
        )
        if project_id is not None:
            kwargs["project_id"] = project_id
        doc = Document(**kwargs)
        db.add(doc)
        await db.flush()
        return UploadResponse(document_id=doc.id, title=doc.title, source_type=doc.source_type)

    async def ingest(self, db: AsyncSession, document_id: uuid.UUID) -> Document:
        pipe = IngestionPipeline(db, self._upload_dir)
        try:
            return await pipe.ingest_document(document_id)
        except ValueError as e:
            msg = str(e)
            if msg.startswith("document not found"):
                raise HTTPException(status_code=404, detail=msg) from e
            raise HTTPException(status_code=400, detail=msg) from e
        except RuntimeError as e:
            raise HTTPException(status_code=502, detail=str(e)) from e
        except Exception as e:
            logger.exception("Unexpected ingest failure doc=%s", document_id)
            raise HTTPException(
                status_code=500,
                detail=f"Ingestion failed: {type(e).__name__}: {e}",
            ) from e

    async def ingest_stream(self, db: AsyncSession, document_id: uuid.UUID) -> AsyncIterator[str]:
        pipe = IngestionPipeline(db, self._upload_dir)
        try:
            async for item in pipe.ingest_document_stream(document_id):
                yield sse_event(item.get("event", "progress"), json.dumps(item))
        except (ValueError, RuntimeError) as e:
            yield sse_event("error", json.dumps({"detail": str(e)}))
        except Exception as e:
            logger.exception("Unexpected ingest failure doc=%s", document_id)
            yield sse_event("error", json.dumps({"detail": f"{type(e).__name__}: {e}"}))

    async def list_documents(self, db: AsyncSession, project_id: uuid.UUID | None = None) -> list[DocumentOut]:
        stmt = select(Document).order_by(Document.ingested_at.desc())
        if project_id is not None:
            stmt = stmt.where(Document.project_id == project_id)
        rows = (await db.execute(stmt)).scalars().all()
        return [DocumentOut.model_validate(r) for r in rows]

    async def delete_document(self, db: AsyncSession, document_id: uuid.UUID) -> None:
        doc = (
            await db.execute(select(Document).where(Document.id == document_id))
        ).scalar_one_or_none()
        if doc is None:
            raise HTTPException(status_code=404, detail="document not found")
        self._vector.delete_document_collection(document_id)
        if doc.storage_path:
            Path(doc.storage_path).unlink(missing_ok=True)
        await db.delete(doc)

    async def delete_all(self, db: AsyncSession) -> int:
        docs = (await db.execute(select(Document))).scalars().all()
        count = len(docs)
        for doc in docs:
            self._vector.delete_document_collection(doc.id)
            if doc.storage_path:
                Path(doc.storage_path).unlink(missing_ok=True)
        await db.execute(text(
            "TRUNCATE mastery_scores, turns, sessions, concept_edges, concepts, documents CASCADE"
        ))
        return count

    async def concept_graph(self, db: AsyncSession, document_id: uuid.UUID) -> ConceptGraphResponse:
        concepts = (
            (await db.execute(select(Concept).where(Concept.document_id == document_id)))
            .scalars()
            .all()
        )
        cids = [c.id for c in concepts]
        edges = (
            (
                await db.execute(
                    select(ConceptEdge).where(
                        or_(
                            ConceptEdge.from_concept_id.in_(cids),
                            ConceptEdge.to_concept_id.in_(cids),
                        )
                    )
                )
            )
            .scalars()
            .all()
        )
        return ConceptGraphResponse(
            document_id=document_id,
            concepts=[ConceptOut.model_validate(c) for c in concepts],
            edges=[ConceptEdgeOut.model_validate(e) for e in edges],
        )
