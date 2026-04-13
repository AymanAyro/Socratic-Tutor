import logging
import uuid
from collections.abc import AsyncIterator

from sqlalchemy.ext.asyncio import AsyncSession

from Models.Content import Concept
from Stores.LLM.PromptRegistry import SOCRATIC_SYSTEM_TEMPLATE, SOCRATIC_USER_TEMPLATE, PromptRegistry
from Stores.LLM.factory import get_generation_client
from Stores.VectorStore import VectorStore
from Utils.ContextManager import ContextManager, TurnLike
from config import get_settings

logger = logging.getLogger(__name__)

_PLACEHOLDER_KEYS = (
    "concept",
    "state",
    "gap",
    "memory",
    "rag_context",
    "previous_questions",
    "session_mode",
)


def _fill_prompt_template(template: str, **kwargs: str) -> str:
    """Replace only known `{key}` placeholders so curly braces in RAG text cannot break formatting."""
    out = template
    for k in _PLACEHOLDER_KEYS:
        if k in kwargs:
            out = out.replace("{" + k + "}", kwargs[k])
    return out


def format_previous_questions(
    memory_turns: list[TurnLike], opening_question: str | None
) -> str:
    """Numbered list of tutor questions already asked (opening + prior turns)."""
    lines: list[str] = []
    n = 0
    if opening_question and opening_question.strip():
        n += 1
        oq = opening_question.strip().replace("\n", " ")
        if len(oq) > 320:
            oq = oq[:317] + "..."
        lines.append(f"{n}. (opening) {oq}")
    for t in memory_turns:
        n += 1
        q = t.question_generated.strip().replace("\n", " ")
        if len(q) > 320:
            q = q[:317] + "..."
        lines.append(f"{n}. {q}")
    if not lines:
        return "(none yet — first tutor question in this session.)"
    return "\n".join(lines)


class QuestionGenerator:
    def __init__(self, db: AsyncSession) -> None:
        self._db = db
        self._gen = get_generation_client()
        self._settings = get_settings()
        self._ctx = ContextManager()
        self._vector = VectorStore()

    async def _load_concept(self, concept_id: uuid.UUID) -> Concept:
        from sqlalchemy import select

        row = (await self._db.execute(select(Concept).where(Concept.id == concept_id))).scalar_one()
        return row

    def _mode_instruction(self, mode: str) -> str:
        m = {
            "deepen": "MODE_LINE: deepen — apply the concept in a harder context.",
            "probe_gap": "MODE_LINE: probe_gap — target exactly the identified gap.",
            "scaffold": "MODE_LINE: scaffold — ask a simpler prerequisite question.",
            "reframe": "MODE_LINE: reframe — approach from a different angle.",
            "micro_explain_then_ask": (
                "MODE_LINE: micro_explain_then_ask — give a brief 2–3 sentence factual clarification "
                "only to unblock the learner, then ask ONE Socratic follow-up question in the same reply."
            ),
        }.get(mode, "")
        return m

    async def generate_stream(
        self,
        session_id: uuid.UUID,
        concept_id: uuid.UUID,
        state: str,
        gap: str | None,
        mode: str,
        memory_turns: list[TurnLike],
        opening_question: str | None,
        student_answer: str,
        session_mode: str = "socratic",
        variation_hint: str | None = None,
    ) -> AsyncIterator[str]:
        concept = await self._load_concept(concept_id)
        rag_context = ""
        try:

            def _q() -> str:
                return self._vector.query_by_concept(
                    concept.document_id, concept_id, student_answer, n_results=5
                )

            import asyncio

            rag_context = await asyncio.to_thread(_q)
        except Exception:
            rag_context = ""
        rag_context = self._ctx.truncate_to_budget(rag_context, 3200)
        memory = self._ctx.build_memory(memory_turns, opening_question) or "No prior turns."
        memory = self._ctx.truncate_to_budget(memory, 2400)
        previous_questions = format_previous_questions(memory_turns, opening_question)

        registry = PromptRegistry(self._db)
        resolved = await registry.get_prompt("socratic", session_id)
        template = resolved.template if resolved.template else SOCRATIC_SYSTEM_TEMPLATE
        system = _fill_prompt_template(template, session_mode=session_mode)
        mode_instruction = self._mode_instruction(mode)
        if mode_instruction:
            system = mode_instruction + "\n\n" + system
        user_context = _fill_prompt_template(
            SOCRATIC_USER_TEMPLATE,
            concept=concept.name,
            state=state,
            gap=(gap.strip() if isinstance(gap, str) and gap.strip() else "none identified"),
            memory=memory,
            rag_context=rag_context or "(no retrieved chunks)",
            previous_questions=previous_questions,
            session_mode=session_mode,
        )
        prompt = (
            f"{user_context}\n\n"
            f'<LATEST_STUDENT_MESSAGE>\n"""{student_answer}"""\n</LATEST_STUDENT_MESSAGE>\n\n'
            "Produce only your next single question (or micro-explain+question if MODE_LINE says so). "
            "Do not echo CONTEXT, MODE_LINE, or field labels; do not output planning or <channel|>."
        )
        if variation_hint and variation_hint.strip():
            prompt += f"\n\n<VARIATION_HINT>{variation_hint.strip()}</VARIATION_HINT>"
        try:
            async for chunk in self._gen.generate_stream(prompt, system=system):
                yield chunk
        except Exception:
            logger.exception("Question generation stream failed")
            yield f"Can you tell me more about what you understand about {concept.name}?"

    async def generate_opening_stream(
        self,
        session_id: uuid.UUID,
        concept: Concept,
        session_mode: str = "socratic",
    ) -> AsyncIterator[str]:
        rag_context = ""
        try:
            seed = concept.description or concept.name

            def _q() -> str:
                return self._vector.query_by_concept(
                    concept.document_id, concept.id, seed, n_results=5
                )

            import asyncio

            rag_context = await asyncio.to_thread(_q)
        except Exception:
            rag_context = ""
        rag_context = self._ctx.truncate_to_budget(rag_context, 3200)
        registry = PromptRegistry(self._db)
        resolved = await registry.get_prompt("socratic", session_id)
        template = resolved.template if resolved.template else SOCRATIC_SYSTEM_TEMPLATE
        system = _fill_prompt_template(template, session_mode=session_mode)
        mode_instruction = self._mode_instruction("probe_gap")
        if mode_instruction:
            system = mode_instruction + "\n\n" + system
        user_context = _fill_prompt_template(
            SOCRATIC_USER_TEMPLATE,
            concept=concept.name,
            state="partial",
            gap="null",
            memory="(Session start — no prior student replies yet.)",
            rag_context=rag_context or "(no retrieved chunks)",
            previous_questions="(none — you are composing the opening question only.)",
            session_mode=session_mode,
        )
        prompt = (
            f"{user_context}\n\n"
            "Ask exactly one opening Socratic question to begin the session. "
            "Do not echo CONTEXT, MODE_LINE, or field labels; do not output planning or <channel|>; "
            "output only the question."
        )
        try:
            async for chunk in self._gen.generate_stream(prompt, system=system):
                yield chunk
        except Exception:
            logger.exception("Opening question stream failed")
            yield f"What comes to mind when you think about {concept.name}?"
