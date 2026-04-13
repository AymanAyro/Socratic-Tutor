import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from Stats.Metrics import REPORT_DOWNLOADS
from Stats.SessionAnalytics import load_session
from database import get_db

router = APIRouter(prefix="/report", tags=["report"])


@router.get("/{session_id}/status")
async def report_status(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    session = await load_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return {
        "session_id": str(session_id),
        "status": getattr(session, "report_status", None) or "none",
        "pdf_path": getattr(session, "report_pdf_path", None),
    }


@router.get("/{session_id}/pdf")
async def report_pdf(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    session = await load_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    path = getattr(session, "report_pdf_path", None)
    if not path or not Path(path).is_file():
        raise HTTPException(status_code=404, detail="Report not ready or file missing")
    REPORT_DOWNLOADS.inc()
    p = Path(path)
    if p.suffix.lower() == ".html":
        return FileResponse(p, media_type="text/html", filename=f"session-{session_id}.html")
    return FileResponse(p, media_type="application/pdf", filename=f"session-{session_id}.pdf")
