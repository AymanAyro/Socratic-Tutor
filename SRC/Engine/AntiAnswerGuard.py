import logging
import re
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from Stores.LLM.PromptRegistry import GUARD_SYSTEM_TEMPLATE, GUARD_USER_TEMPLATE, PromptRegistry
from Stores.LLM.factory import get_generation_client
from config import get_settings

logger = logging.getLogger(__name__)


def interpret_guard_model_output(raw: str) -> bool:
    """
    Map guard LLM text to pass/fail for the proposed tutor line.
    Pass (return True) = question does not violate the no-answer rule (model should say NO).
    """
    text = (raw or "").strip()
    text = re.sub(r"```(?:\w*)?\n?", "", text)
    text = text.replace("```", "")
    upper = text.upper()
    matches = list(re.finditer(r"\b(YES|NO)\b", upper))
    if not matches:
        logger.debug("AntiAnswerGuard: no YES/NO token in response; allowing question. raw=%r", raw[:400])
        return True
    last = matches[-1].group(1)
    return last == "NO"


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
            system = template
            user_prompt = (
                GUARD_USER_TEMPLATE.replace("{question}", question).replace("{concept}", concept)
                + "\n\nRespond with exactly one word: YES or NO."
            )
            text, tokens = await self._client.generate(
                user_prompt,
                system=system,
                model=self._settings.classifier_model_id,
            )
            passes = interpret_guard_model_output(text)
            logger.debug(
                "AntiAnswerGuard session_id=%s passes=%s raw_head=%r",
                session_id,
                passes,
                (text or "")[:240],
            )
            return passes, tokens
        except Exception:
            logger.exception("AntiAnswerGuard failed, allowing question through")
            return True, 0
