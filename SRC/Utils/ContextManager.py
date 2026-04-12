from dataclasses import dataclass

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

    def build_memory(self, turns: list[TurnLike], opening_question: str | None = None) -> str:
        parts: list[str] = []
        if opening_question:
            parts.append(f"Tutor (opening): {opening_question}")
        if not turns:
            return "\n".join(parts).strip()
        recent = turns[-self.MAX_RAW_TURNS :]
        older = turns[: -self.MAX_RAW_TURNS]
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
