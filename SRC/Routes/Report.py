from datetime import datetime, timezone
import uuid
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from Models.Content import Concept
from Models.Session import MasteryScore
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


@router.get("/{session_id}/summary")
async def report_summary(
    request: Request,
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    session = await load_session(db, session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    graph = getattr(request.app.state, "teaching_graph", None)
    analyst = None
    if graph is not None:
        cfg = {
            "configurable": {
                "thread_id": str(session_id),
                "db": db,
                "redis": None,
                "asset_store": getattr(request.app.state, "stage2_asset_store", {}),
            }
        }
        snap = await graph.aget_state(cfg)
        analyst = (snap.values or {}).get("analyst_json")
    concept = (
        await db.execute(select(Concept).where(Concept.id == session.concept_id))
    ).scalar_one_or_none()
    review_schedule: list[dict[str, str | int | float]] = []
    if session.user_id is not None:
        mastery = (
            await db.execute(
                select(MasteryScore)
                .where(MasteryScore.user_id == session.user_id, MasteryScore.concept_id == session.concept_id)
                .order_by(MasteryScore.next_review_date.asc().nullslast())
                .limit(1)
            )
        ).scalar_one_or_none()
        if mastery is not None and mastery.next_review_date is not None:
            review_schedule.append(
                {
                    "concept_name": concept.name if concept else "Concept",
                    "days_until": max(
                        0,
                        (mastery.next_review_date - datetime.now(timezone.utc).date()).days,
                    ),
                    "review_date": mastery.next_review_date.isoformat(),
                    "mastery_score": float(mastery.score or 0.0),
                }
            )
    return {
        "session_id": str(session_id),
        "status": getattr(session, "report_status", None) or "none",
        "analyst": analyst or {},
        "review_schedule": review_schedule,
        "session_name": getattr(session, "name", None),
    }
