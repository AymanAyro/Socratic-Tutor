import asyncio
import hashlib
import json
import logging
import uuid
from dataclasses import dataclass

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field, field_validator
from redis.asyncio import Redis
from sqlalchemy.ext.asyncio import AsyncSession

from Stores.LLM.PromptRegistry import PromptRegistry
from Stores.LLM.factory import get_generation_client
from Stores.LLM.langchain_factory import classifier_structured_model
from config import get_settings

logger = logging.getLogger(__name__)


def _strip_json_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        parts = t.split("\n", 1)
        t = parts[1] if len(parts) > 1 else t
        t = t.rsplit("```", 1)[0]
    return t.strip()


class ClassifierOutput(BaseModel):
    state: str
    confidence: float = Field(ge=0, le=1)
    gap: str | None = None

    @field_validator("state")
    @classmethod
    def valid_state(cls, v: str) -> str:
        allowed = {"correct", "partial", "wrong", "stuck"}
        if v not in allowed:
            raise ValueError("invalid state")
        return v

    @field_validator("gap")
    @classmethod
    def valid_gap(cls, v: str | None, info) -> str | None:
        state = info.data.get("state") if info and info.data else None
        if state in {"partial", "wrong"}:
            if v is None or not str(v).strip():
                raise ValueError("gap must be a non-empty string for partial/wrong")
            return str(v).strip()
        if state in {"correct", "stuck"}:
            return None
        return v


@dataclass
class ClassifierResult:
    state: str
    confidence: float
    gap: str | None
    tokens_used: int


def _usage_tokens(msg) -> int:
    um = getattr(msg, "usage_metadata", None) or {}
    return int(
        um.get("total_tokens")
        or (um.get("input_tokens", 0) + um.get("output_tokens", 0))
        or 0
    )


class UnderstandingClassifier:
    CACHE_TTL = 3600

    def __init__(self, db: AsyncSession, redis: Redis | None = None) -> None:
        self._db = db
        self._redis = redis
        self._settings = get_settings()
        self._fallback_client = get_generation_client()

    def _cache_key(self, concept_id: uuid.UUID, answer: str) -> str:
        h = hashlib.sha256(answer.encode()).hexdigest()[:24]
        return f"cls:{concept_id}:{h}"

    async def classify(
        self,
        concept_id: uuid.UUID,
        concept_name: str,
        student_answer: str,
        session_id: uuid.UUID,
    ) -> ClassifierResult:
        key = self._cache_key(concept_id, student_answer)
        if self._redis:
            cached = await self._redis.get(key)
            if cached:
                data = json.loads(cached)
                return ClassifierResult(
                    state=data["state"],
                    confidence=data["confidence"],
                    gap=data.get("gap"),
                    tokens_used=0,
                )

        registry = PromptRegistry(self._db)
        resolved = await registry.get_prompt("classifier", session_id)
        user_prompt = f'Concept being assessed: "{concept_name}"\nStudent response:\n{student_answer}'
        messages = [
            SystemMessage(content=resolved.template),
            HumanMessage(content=user_prompt),
        ]

        def _run_langchain() -> tuple[ClassifierOutput, int]:
            base = classifier_structured_model()
            if self._settings.generation_backend.upper() == "GEMINI":
                structured = base.with_structured_output(
                    ClassifierOutput,
                    method="json_schema",
                    include_raw=True,
                )
            else:
                structured = base.with_structured_output(ClassifierOutput, include_raw=True)
            out = structured.invoke(messages)
            if isinstance(out, dict):
                parsed = out.get("parsed")
                raw = out.get("raw")
                if not isinstance(parsed, ClassifierOutput):
                    raise ValueError("structured classify parse failed")
                return parsed, _usage_tokens(raw) if raw is not None else 0
            if isinstance(out, ClassifierOutput):
                return out, 0
            raise ValueError("unexpected structured output")

        try:
            out, tokens = await asyncio.to_thread(_run_langchain)
        except Exception:
            logger.warning("Structured classify failed, trying fallback", exc_info=True)
            try:
                text, tokens = await self._fallback_client.generate(
                    user_prompt,
                    system=resolved.template,
                    model=self._settings.classifier_model_id,
                    json_mode=True,
                )
                data = json.loads(_strip_json_fence(text))
                out = ClassifierOutput.model_validate(data)
            except Exception:
                logger.exception("Classifier fallback also failed, returning safe default")
                return ClassifierResult(
                    state="partial",
                    confidence=0.5,
                    gap=f"the student has not fully explained the core mechanism of {concept_name}",
                    tokens_used=0,
                )

        gap = out.gap
        if out.state in {"partial", "wrong"} and not (gap or "").strip():
            gap = f"the student has not fully explained the core mechanism of {concept_name}"
        result = ClassifierResult(
            state=out.state,
            confidence=out.confidence,
            gap=gap,
            tokens_used=tokens,
        )
        if self._redis:
            await self._redis.setex(
                key,
                self.CACHE_TTL,
                json.dumps({"state": result.state, "confidence": result.confidence, "gap": result.gap}),
            )
        return result
