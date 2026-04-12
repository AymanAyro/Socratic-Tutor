import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from Stores.LLM.PromptRegistry import GUARD_SYSTEM_TEMPLATE, PromptRegistry
from Stores.LLM.factory import get_generation_client
from config import get_settings

logger = logging.getLogger(__name__)


class AntiAnswerGuard:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._client = get_generation_client()
        self._settings = get_settings()

    async def check_passes(self, question: str, concept: str, session_id: uuid.UUID) -> tuple[bool, int]:
        try:
            registry = PromptRegistry(self._db)
            resolved = await registry.get_prompt("guard", session_id)
            template = resolved.template if resolved.template else GUARD_SYSTEM_TEMPLATE
            system = template.replace("{question}", question).replace("{concept}", concept)
            text, tokens = await self._client.generate(
                "Respond with exactly one word: YES or NO.",
                system=system,
                model=self._settings.classifier_model_id,
            )
            normalized = text.strip().upper()
            passes = normalized.startswith("NO")
            return passes, tokens
        except Exception:
            logger.exception("AntiAnswerGuard failed, allowing question through")
            return True, 0
