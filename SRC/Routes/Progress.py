import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from Controllers.ProgressController import ProgressController
from Models.Schemas import DueConceptOut, MasteryOut, ProgressHistoryOut
from database import get_db

router = APIRouter(prefix="/progress", tags=["progress"])


@router.get("/mastery/{user_id}", response_model=list[MasteryOut])
async def get_mastery(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    ctrl = ProgressController()
    return await ctrl.mastery_for_user(db, user_id)


@router.get("/due", response_model=list[DueConceptOut])
async def due_reviews(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    ctrl = ProgressController()
    return await ctrl.due_concepts(db, user_id)


@router.get("/session/{session_id}/summary")
async def session_summary(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    ctrl = ProgressController()
    text = await ctrl.session_summary(db, session_id)
    return {"session_id": str(session_id), "summary": text}


@router.get("/history/{user_id}", response_model=ProgressHistoryOut)
async def progress_history(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    ctrl = ProgressController()
    return await ctrl.user_history(db, user_id)
