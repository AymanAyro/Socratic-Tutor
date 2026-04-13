import logging
import re

from Stores.LLM.factory import get_generation_client
from config import get_settings

logger = logging.getLogger(__name__)

CLARIFICATION_SYSTEM = """
You are an educational assistant helping a student understand what a Socratic
tutor question is asking them to think about.

Write a clarification in 2-4 sentences that explains:
1. What specific concept or idea this question is probing
2. What a complete, strong answer would need to include
3. Why this question is important for understanding the topic

Do NOT answer the question itself. Do NOT give the answer away.
Write for the student - use "this question asks you to..." framing.
Be concrete and specific to the concept, not generic.
Write only the clarification paragraph. No headings, no lists.
"""

TURN_DIAGRAM_SYSTEM = """
You are an educational diagram designer. Generate a focused Mermaid diagram
that visually explains the specific concept this Socratic question is probing.

Rules:
- Scope to this single concept or sub-concept only - not the entire topic
- Use flowchart TD or graph LR
- Maximum 7 nodes. Labels under 5 words each.
- Show mechanism or relationship, not a list of terms
- No title node, no legend nodes
- Output only the raw Mermaid code. Nothing else.
"""


def _strip_code_fence(raw: str) -> str:
    text = (raw or "").strip()
    if text.startswith("```"):
        lines = text.splitlines()
        if lines:
            lines = lines[1:]
        while lines and lines[-1].strip().startswith("```"):
            lines = lines[:-1]
        text = "\n".join(lines).strip()
    return text


def _safe_clarification(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", (text or "").strip())
    if not cleaned:
        return "This question asks you to focus on the core idea and explain the relationship clearly using evidence from what you already know."
    return cleaned[:900]


async def generate_clarification(topic: str, question: str, prior_answer: str) -> str:
    settings = get_settings()
    system = CLARIFICATION_SYSTEM
    prompt = (
        f"Topic: {topic}\n"
        f"The tutor just asked: {question[:900]}\n"
        f"The student's prior answer (for context): {prior_answer[:1200]}\n\n"
        "Write the clarification now."
    )
    gen = get_generation_client()
    text, _ = await gen.generate(
        prompt=prompt,
        system=system,
        model=settings.generation_model_id,
    )
    return _safe_clarification(text)


async def generate_turn_diagram(topic: str, question: str) -> str:
    settings = get_settings()
    system = TURN_DIAGRAM_SYSTEM
    prompt = (
        f"Topic: {topic[:200]}\n"
        f"Concept being probed by this question: {question[:700]}\n\n"
        "Output only valid Mermaid."
    )
    gen = get_generation_client()
    text, _ = await gen.generate(
        prompt=prompt,
        system=system,
        model=settings.generation_model_id,
    )
    raw = _strip_code_fence(text or "")
    return raw or f'flowchart TD\n  A["{topic[:40]}"]'
