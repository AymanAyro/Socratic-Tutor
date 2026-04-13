from dataclasses import dataclass
from typing import Any

from langchain_core.messages import AIMessage, HumanMessage

from config import get_settings


@dataclass
class TurnLike:
    student_input: str
    question_generated: str


class ContextManager:
    MAX_RAW_TURNS = 3

    def __init__(self) -> None:
        self._settings = get_settings()
        self.MAX_RAW_TURNS = self._settings.context_max_raw_turns

    def _text(self, value: Any) -> str:
        if value is None:
            return ""
        if isinstance(value, str):
            return value.strip()
        return str(value).strip()

    def _turns_from_messages(self, messages: list[Any]) -> tuple[str | None, list[TurnLike]]:
        inferred_opening: str | None = None
        turns: list[TurnLike] = []
        if not messages:
            return inferred_opening, turns

        idx = 0
        first = messages[0]
        if isinstance(first, AIMessage):
            inferred_opening = self._text(first.content)
            idx = 1

        pending_student: str | None = None
        for m in messages[idx:]:
            if isinstance(m, HumanMessage):
                pending_student = self._text(m.content)
                continue
            if isinstance(m, AIMessage) and pending_student:
                turns.append(TurnLike(student_input=pending_student, question_generated=self._text(m.content)))
                pending_student = None
        return inferred_opening, turns

    def build_memory(self, turns: list[TurnLike] | list[Any], opening_question: str | None = None) -> str:
        normalized_turns: list[TurnLike]
        if turns and isinstance(turns[0], TurnLike):
            normalized_turns = turns  # type: ignore[assignment]
        elif turns and isinstance(turns[0], (AIMessage, HumanMessage)):
            inferred_opening, msg_turns = self._turns_from_messages(turns)
            if not opening_question and inferred_opening:
                opening_question = inferred_opening
            normalized_turns = msg_turns
        else:
            normalized_turns = []

        parts: list[str] = []
        if opening_question:
            parts.append(f"Tutor (opening): {opening_question}")
        if not normalized_turns:
            return "\n".join(parts).strip()
        recent = normalized_turns[-self.MAX_RAW_TURNS :]
        older = normalized_turns[: -self.MAX_RAW_TURNS]
        if older:
            parts.append(self._summarise_older(older))
        for t in recent:
            parts.append(f"Student: {t.student_input}\nTutor: {t.question_generated}")
        return "\n".join(parts).strip()

    def _summarise_older(self, turns: list[TurnLike]) -> str:
        # Single sentence summary without extra LLM call in v1
        n = len(turns)
        return f"[Earlier dialogue: {n} prior turn(s) omitted for brevity.]"

    def truncate_to_budget(self, text: str, max_chars: int) -> str:
        if len(text) <= max_chars:
            return text
        return text[: max_chars - 3] + "..."
