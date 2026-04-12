import logging
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from Controllers.IngestionController import IngestionController
from Models.Schemas import ConceptGraphResponse, DocumentOut, UploadResponse
from database import AsyncSessionLocal, get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/content", tags=["content"])


@router.post("/upload", response_model=UploadResponse)
async def upload_content(
    file: UploadFile = File(...),
    project_id: Optional[str] = Form(None),
    db: AsyncSession = Depends(get_db),
):
    ctrl = IngestionController()
    pid = uuid.UUID(project_id) if project_id else None
    return await ctrl.upload(db, file, project_id=pid)


@router.post("/ingest/{doc_id}")
async def ingest_document(doc_id: uuid.UUID):
    ctrl = IngestionController()

    async def gen():
        async with AsyncSessionLocal() as db:
            try:
                async for chunk in ctrl.ingest_stream(db, doc_id):
                    yield chunk
                await db.commit()
            except Exception:
                await db.rollback()
                raise

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.get("/documents", response_model=list[DocumentOut])
async def list_documents(
    project_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    ctrl = IngestionController()
    return await ctrl.list_documents(db, project_id=project_id)


@router.delete("/document/{doc_id}")
async def delete_document(
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    ctrl = IngestionController()
    await ctrl.delete_document(db, doc_id)
    return {"deleted": str(doc_id)}


@router.delete("/all")
async def delete_all(
    db: AsyncSession = Depends(get_db),
):
    ctrl = IngestionController()
    count = await ctrl.delete_all(db)
    return {"deleted_documents": count}


@router.get("/concepts/{doc_id}", response_model=ConceptGraphResponse)
async def get_concepts(
    doc_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    ctrl = IngestionController()
    return await ctrl.concept_graph(db, doc_id)
