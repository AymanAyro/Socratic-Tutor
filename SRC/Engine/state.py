"""LangGraph teaching state (Stage 2)."""

from typing import Annotated, Any

from langchain_core.messages import AnyMessage
from langgraph.graph.message import add_messages
from typing_extensions import TypedDict


def merge_dict(a: dict | None, b: dict | None) -> dict[str, Any]:
    out = dict(a or {})
    for k, v in (b or {}).items():
        if v is not None:
            out[k] = v
    return out


def or_bool(a: bool | None, b: bool | None) -> bool:
    return bool(a) or bool(b)


def replace_str(_previous: str, new: str) -> str:
    """Last-wins merge for LangGraph when multiple tasks set the same key in one step."""
    return new


class TeachingState(TypedDict, total=False):
    """Checkpointed state for the single-concept Stage 2 arc."""

    messages: Annotated[list[AnyMessage], add_messages]
    session_id: str
    user_id: str
    concept_id: str
    concept_name: str
    document_id: str
    difficulty_level: int
    max_probe_turns: int
    phase: Annotated[str, replace_str]  # PROBE | REVEAL | REFLECT | CONSOLIDATE | END
    opening_question: str
    prompt_version: str
    session_mode: str
    probe_turns: int
    mastery_signal: bool
    last_classifier_state: str
    last_classifier_confidence: float
    self_rating: int | None
    background_dispatched: Annotated[bool, or_bool]
    reveal_assets: Annotated[dict[str, Any], merge_dict]
    session_stats: Annotated[dict[str, Any], merge_dict]
    consolidate_attempts: int
    last_consolidate_state: str
    consolidation_question: str
    needs_report: bool
    report_pdf_path: str | None
    report_status: str | None
    analyst_json: dict[str, Any] | None
    force_reveal: bool
