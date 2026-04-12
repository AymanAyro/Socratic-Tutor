import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from Models.Session import MasteryScore
from Pipelines.SpacedRepetition import SM2, state_to_quality
from Stats.Metrics import MASTERY_SCORE


class MasteryTracker:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._sm2 = SM2()

    async def apply_classifier_state(
        self,
        user_id: uuid.UUID,
        concept_id: uuid.UUID,
        state: str,
        session_id: uuid.UUID | None = None,
    ) -> MasteryScore:
        q = select(MasteryScore).where(
            MasteryScore.user_id == user_id,
            MasteryScore.concept_id == concept_id,
        )
        row = (await self._db.execute(q)).scalar_one_or_none()
        if row is None:
            row = MasteryScore(
                user_id=user_id,
                concept_id=concept_id,
                session_id=session_id,
                score=0.0,
                repetitions=0,
                easiness_factor=2.5,
                interval_days=1,
            )
            self._db.add(row)
            await self._db.flush()

        quality = state_to_quality(state)
        self._sm2.update(row, quality)
        row.session_id = session_id
        row.score = min(1.0, row.score + {5: 0.15, 3: 0.05, 1: -0.05, 0: -0.02}.get(quality, 0))
        row.score = max(0.0, row.score)
        MASTERY_SCORE.labels(concept_id=str(concept_id)).set(row.score)
        return row
