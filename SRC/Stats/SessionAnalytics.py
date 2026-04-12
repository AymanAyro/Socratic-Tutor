import uuid

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from Models.Session import Turn, TutorSession


async def session_turn_count(db: AsyncSession, session_id: uuid.UUID) -> int:
    q = select(func.count()).select_from(Turn).where(Turn.session_id == session_id)
    return int((await db.execute(q)).scalar_one())


async def load_session(db: AsyncSession, session_id: uuid.UUID) -> TutorSession | None:
    return (await db.execute(select(TutorSession).where(TutorSession.id == session_id))).scalar_one_or_none()
