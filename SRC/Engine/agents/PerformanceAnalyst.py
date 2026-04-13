import json
import logging
import re
import uuid

from sqlalchemy.ext.asyncio import AsyncSession

from Stores.LLM.factory import get_generation_client
from config import get_settings

logger = logging.getLogger(__name__)

ANALYST_SYSTEM = """You are an educational performance analyst. Analyse this session and produce
a structured JSON assessment.

Output a JSON object with exactly these fields:
{{
  "overall_performance": "struggling" | "developing" | "solid" | "strong",
  "strongest_concept": string,
  "weakest_concept": string,
  "insight": "2-3 sentence personalised observation about this student's learning pattern",
  "recommendations": ["3 specific, actionable study recommendations"],
  "dunning_kruger_flag": bool,
  "concepts_to_review": ["concept ids due before next session"]
}}

If the student's self-rating is 2 or more points higher than classifier confidence suggests,
set dunning_kruger_flag to true and include in insight that the student may be
overestimating understanding. Keep this constructive and actionable.

Output only the JSON object."""


def _strip_json_fence(text: str) -> str:
    t = text.strip()
    if t.startswith("```"):
        t = re.sub(r"^```\w*\n?", "", t)
        t = re.sub(r"\n?```$", "", t)
    return t.strip()


async def analyse_session_performance(
    db: AsyncSession,
    *,
    session_id: uuid.UUID,
    payload: dict,
) -> dict:
    settings = get_settings()
    system = ANALYST_SYSTEM
    prompt = (
        "Session data:\n"
        f"- Concepts covered: {json.dumps(payload.get('concepts', []))}\n"
        f"- Per-concept probe turns: {json.dumps(payload.get('probe_turns_per_concept', {}))}\n"
        f"- Classifier state sequences: {json.dumps(payload.get('classifier_sequences', {}))}\n"
        f"- Self-ratings vs classifier confidence: {json.dumps(payload.get('rating_gap', {}))}\n"
        f"- Escape hatch activations: {payload.get('escape_hatch_count', 0)}\n"
        f"- Mastery scores before and after: {json.dumps(payload.get('mastery_delta', {}))}\n\n"
        "Respond with JSON only."
    )
    gen = get_generation_client()
    text, _ = await gen.generate(
        prompt=prompt,
        system=system,
        model=settings.generation_model_id,
        json_mode=True,
    )
    try:
        return json.loads(_strip_json_fence(text or "{}"))
    except json.JSONDecodeError:
        logger.exception("Analyst JSON parse failed")
        return {
            "overall_performance": "developing",
            "strongest_concept": "",
            "weakest_concept": "",
            "insight": "Keep practicing with spaced review.",
            "recommendations": [
                "Review the concept summary in your session report.",
                "Revisit weak areas with the source material.",
                "Schedule a follow-up session soon.",
            ],
            "dunning_kruger_flag": False,
            "concepts_to_review": [],
        }
