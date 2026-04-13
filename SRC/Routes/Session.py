import uuid

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import Response, StreamingResponse
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from Controllers.SessionController import SessionController
from Models.Schemas import (
    ReflectRequest,
    SessionEndResponse,
    SessionHistoryItem,
    SessionPhaseOut,
    SessionStartRequest,
    SessionStartResponse,
    TurnClarificationOut,
    TurnOut,
    TurnRequest,
)
from database import AsyncSessionLocal, get_db
from deps import get_redis

router = APIRouter(prefix="/session", tags=["session"])


@router.post("/start", response_model=SessionStartResponse)
async def start_session(
    request: Request,
    body: SessionStartRequest,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    ctrl = SessionController()
    g = getattr(request.app.state, "teaching_graph", None)
    store = getattr(request.app.state, "stage2_asset_store", None)
    return await ctrl.start_session(
        db,
        body,
        redis=redis,
        teaching_graph=g,
        stage2_asset_store=store,
    )


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


@router.get("/turn/{turn_id}/clarification", response_model=TurnClarificationOut)
async def turn_clarification(
    turn_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    ctrl = SessionController()
    return await ctrl.get_turn_clarification(db, turn_id)


@router.get("/{session_id}/phase", response_model=SessionPhaseOut)
async def session_phase(
    request: Request,
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    ctrl = SessionController()
    g = getattr(request.app.state, "teaching_graph", None)
    store = getattr(request.app.state, "stage2_asset_store", None)
    return await ctrl.get_teaching_phase(
        db,
        session_id,
        teaching_graph=g,
        stage2_asset_store=store,
    )


@router.get("/{session_id}/diagram/{concept_id}")
async def session_diagram(
    request: Request,
    session_id: uuid.UUID,
    concept_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    g = getattr(request.app.state, "teaching_graph", None)
    if g is None:
        raise HTTPException(status_code=503, detail="Teaching graph unavailable")
    cfg = {
        "configurable": {
            "thread_id": str(session_id),
            "db": db,
            "redis": None,
            "asset_store": getattr(request.app.state, "stage2_asset_store", {}),
        }
    }
    snap = await g.aget_state(cfg)
    vals = snap.values or {}
    if str(vals.get("concept_id") or "") != str(concept_id):
        raise HTTPException(status_code=404, detail="Concept not found")
    last_reveal = vals.get("reveal_assets") or {}
    svg = str(last_reveal.get("diagram_svg") or "").strip()
    if not svg:
        raise HTTPException(status_code=404, detail="Diagram not ready")
    return Response(content=svg, media_type="image/svg+xml")


@router.post("/{session_id}/reveal", response_model=SessionPhaseOut)
async def session_reveal_early(
    request: Request,
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    ctrl = SessionController()
    g = getattr(request.app.state, "teaching_graph", None)
    store = getattr(request.app.state, "stage2_asset_store", None)
    return await ctrl.reveal_early(
        db,
        session_id,
        teaching_graph=g,
        stage2_asset_store=store,
        redis=redis,
    )


@router.post("/{session_id}/reflect", response_model=SessionPhaseOut)
async def session_reflect(
    request: Request,
    session_id: uuid.UUID,
    body: ReflectRequest,
    db: AsyncSession = Depends(get_db),
):
    ctrl = SessionController()
    g = getattr(request.app.state, "teaching_graph", None)
    store = getattr(request.app.state, "stage2_asset_store", None)
    return await ctrl.submit_reflect(
        db,
        session_id,
        body,
        teaching_graph=g,
        stage2_asset_store=store,
    )


@router.post("/{session_id}/turn")
async def session_turn(
    request: Request,
    session_id: uuid.UUID,
    body: TurnRequest,
    redis: Redis = Depends(get_redis),
):
    ctrl = SessionController()
    g = getattr(request.app.state, "teaching_graph", None)
    store = getattr(request.app.state, "stage2_asset_store", None)

    async def gen():
        async with AsyncSessionLocal() as db:
            try:
                async for chunk in ctrl.stream_turn(
                    db,
                    redis,
                    session_id,
                    body.answer,
                    teaching_graph=g,
                    stage2_asset_store=store,
                ):
                    yield chunk
                await db.commit()
            except Exception:
                await db.rollback()
                raise

    return StreamingResponse(gen(), media_type="text/event-stream")


@router.post("/{session_id}/end", response_model=SessionEndResponse)
async def end_session(
    request: Request,
    session_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
):
    ctrl = SessionController()
    g = getattr(request.app.state, "teaching_graph", None)
    store = getattr(request.app.state, "stage2_asset_store", None)
    return await ctrl.end_session(
        db,
        session_id,
        teaching_graph=g,
        stage2_asset_store=store,
        redis=redis,
    )
