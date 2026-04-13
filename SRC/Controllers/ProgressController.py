import uuid
from datetime import date

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from Models.Content import Concept
from Models.Session import MasteryScore, TutorSession
from Models.Schemas import DueConceptOut, MasteryOut, ProgressHistoryOut


class ProgressController:
    async def mastery_for_user(self, db: AsyncSession, user_id: uuid.UUID) -> list[MasteryOut]:
        rows = (
            await db.execute(
                select(MasteryScore, Concept)
                .join(Concept, Concept.id == MasteryScore.concept_id)
                .where(MasteryScore.user_id == user_id)
            )
        ).all()
        out: list[MasteryOut] = []
        for mastery, concept in rows:
            out.append(
                MasteryOut(
                    concept_id=mastery.concept_id,
                    concept_name=concept.name,
                    score=mastery.score,
                    repetitions=mastery.repetitions,
                    easiness_factor=mastery.easiness_factor,
                    next_review_date=mastery.next_review_date,
                )
            )
        return out

    async def due_concepts(self, db: AsyncSession, user_id: uuid.UUID) -> list[DueConceptOut]:
        today = date.today()
        rows = (
            (
                await db.execute(
                    select(MasteryScore, Concept)
                    .join(Concept, Concept.id == MasteryScore.concept_id)
                    .where(
                        MasteryScore.user_id == user_id,
                        MasteryScore.next_review_date.is_not(None),
                        MasteryScore.next_review_date <= today,
                    )
                )
            )
            .all()
        )
        out: list[DueConceptOut] = []
        for ms, c in rows:
            out.append(
                DueConceptOut(
                    concept_id=c.id,
                    name=c.name,
                    next_review_date=ms.next_review_date,  # type: ignore[arg-type]
                    score=float(ms.score or 0.0),
                )
            )
        return out

    async def session_summary(self, db: AsyncSession, session_id: uuid.UUID) -> str | None:
        s = (
            await db.execute(select(TutorSession).where(TutorSession.id == session_id))
        ).scalar_one_or_none()
        return s.summary_text if s else None

    async def user_history(self, db: AsyncSession, user_id: uuid.UUID) -> ProgressHistoryOut:
        from Controllers.SessionController import SessionController

        mastery = await self.mastery_for_user(db, user_id)
        sessions = await SessionController().list_sessions(db, user_id=user_id)
        return ProgressHistoryOut(mastery=mastery, sessions=sessions)
