import uuid

from fastapi import APIRouter, Depends
from fastapi.responses import StreamingResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from Controllers.SessionController import SessionController
from Models.Schemas import SessionEndResponse, SessionHistoryItem, SessionStartRequest, SessionStartResponse, TurnOut, TurnRequest
from database import AsyncSessionLocal, get_db
from deps import get_redis

router = APIRouter(prefix="/session", tags=["session"])


@router.post("/start", response_model=SessionStartResponse)
async def start_session(
    body: SessionStartRequest,
    db: AsyncSession = Depends(get_db),
):
    ctrl = SessionController()
    return await ctrl.start_session(db, body)


@router.get("/history", response_model=list[SessionHistoryItem])
async def session_history(
    user_id: uuid.UUID | None = None,
    concept_id: uuid.UUID | None = None,
    db: AsyncSession = Depends(get_db),
):
    ctrl = SessionController()
    return await ctrl.list_sessions(db, user_id=user_id, concept_id=concept_id)


@router.get("/{session_id}/turns", response_model=list[TurnOut])
async def session_turns(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    ctrl = SessionController()
    return await ctrl.list_turns(db, session_id)


@router.post("/{session_id}/turn")
async def session_turn(
    session_id: uuid.UUID,
    body: TurnRequest,
    redis: Redis = Depends(get_redis),
):
    ctrl = SessionController()

    async def gen():
        async with AsyncSessionLocal() as db:
            try:
                async for chunk in ctrl.stream_turn(db, redis, session_id, body.answer):
                    yield chunk
                await db.commit()
            except Exception:
                await db.rollback()
                raise

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.post("/{session_id}/end", response_model=SessionEndResponse)
async def end_session(
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    ctrl = SessionController()
    return await ctrl.end_session(db, session_id)
