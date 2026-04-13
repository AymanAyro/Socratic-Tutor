import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from Models.Content import Concept
from Stores.LLM.factory import get_generation_client
from Stores.VectorStore import VectorStore
from Utils.ContextManager import ContextManager
from config import get_settings

logger = logging.getLogger(__name__)

IDEAL_ANSWER_SYSTEM = """You are an expert teacher writing a model answer for a student who has just
attempted to answer questions about the following concept.

Your answer must:
- Be complete and correct, grounded only in the provided source material
- Be appropriate for difficulty tier {difficulty}/5
- Be structured: one clear statement of the core idea, then supporting explanation
- Be concise: 100-200 words maximum
- NOT reference the student's attempt or the Socratic dialogue

Concept: {concept}
Source material: {rag_context}

Write the model answer only. No preamble."""


async def generate_ideal_answer(
    db: AsyncSession,
    concept_id: uuid.UUID,
    *,
    difficulty: int = 1,
) -> str:
    settings = get_settings()
    concept = (await db.execute(select(Concept).where(Concept.id == concept_id))).scalar_one()
    rag_context = ""
    try:
        vector = VectorStore()
        seed = concept.description or concept.name

        def _q() -> str:
            return vector.query_by_concept(concept.document_id, concept_id, seed, n_results=5)

        import asyncio

        rag_context = await asyncio.to_thread(_q)
    except Exception:
        logger.exception("RAG for ideal answer failed")
        rag_context = ""
    rag_context = ContextManager().truncate_to_budget(rag_context, 3200)
    system = IDEAL_ANSWER_SYSTEM.format(
        difficulty=max(1, min(5, difficulty)),
        concept=concept.name,
        rag_context=rag_context or "(no retrieved chunks)",
    )
    gen = get_generation_client()
    text, _ = await gen.generate(
        prompt="Write the model answer now.",
        system=system,
        model=settings.generation_model_id,
    )
    return (text or "").strip() or f"{concept.name}: see your course materials for the full explanation."
