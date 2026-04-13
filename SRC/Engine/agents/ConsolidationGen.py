import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from Stores.LLM.factory import get_generation_client
from config import get_settings


async def generate_consolidation_question(
    db: AsyncSession,
    session_id: uuid.UUID,
    *,
    concept_name: str,
    ideal_answer: str,
    self_rating: int,
) -> str:
    settings = get_settings()
    system = (
        "You are a tutor. The student has seen the full model answer and rated their understanding.\n"
        "Ask exactly ONE short question that checks whether they understood the explanation — "
        "not a repeat of the Socratic probe. The answer should be easy to verify from the model answer.\n"
        f"Concept: {concept_name}\n"
        f"Model answer (excerpt): {ideal_answer[:1200]}\n"
        f"Self-rating (1-5): {self_rating}\n"
    )
    gen = get_generation_client()
    text, _ = await gen.generate(
        prompt="Write only the single consolidation question, no preamble.",
        system=system,
        model=settings.generation_model_id,
    )
    return (text or "").strip() or f"In your own words, what is the main idea behind {concept_name}?"
