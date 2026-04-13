import logging
import uuid

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from Models.Content import Concept
from Stores.LLM.factory import get_generation_client
from config import get_settings

logger = logging.getLogger(__name__)

DIAGRAM_SYSTEM = """You are an educational diagram designer. Generate a Mermaid diagram that visually
explains the following concept to a student.

Rules:
- Use flowchart TD or graph LR — whichever fits the concept structure better
- Maximum 10 nodes. Every node label must be under 6 words.
- Show the mechanism, not a list: cause → effect, components → relationships, steps → order
- No title node. No legend nodes.
- Output only the raw Mermaid code. Nothing else.
"""


async def generate_concept_diagram_mermaid(db: AsyncSession, concept_id: uuid.UUID) -> str:
    concept = (await db.execute(select(Concept).where(Concept.id == concept_id))).scalar_one()
    settings = get_settings()
    system = DIAGRAM_SYSTEM
    prompt = (
        f"Concept: {concept.name}\n"
        f"Description: {(concept.description or concept.name)[:800]}\n\n"
        "Output only valid Mermaid."
    )
    gen = get_generation_client()
    text, _ = await gen.generate(
        prompt=prompt,
        system=system,
        model=settings.generation_model_id,
    )
    raw = (text or "").strip()
    if raw.startswith("```"):
        parts = raw.split("\n", 1)
        raw = parts[1] if len(parts) > 1 else raw
        raw = raw.rsplit("```", 1)[0].strip()
    return raw or f'flowchart TD\n  A["{concept.name[:40]}"]'
