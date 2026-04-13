"""Conditional edges for the Stage 2 teaching graph."""

from langgraph.graph import END

from Engine.state import TeachingState


def route_ingress(state: TeachingState) -> str:
    if state.get("end_requested"):
        return "report_work"
    phase = state.get("phase", "PROBE")
    if phase == "CONSOLIDATE":
        return "consolidate_turn"
    if phase != "PROBE":
        return END
    msgs = state.get("messages") or []
    if not msgs:
        return END
    from langchain_core.messages import HumanMessage

    if not isinstance(msgs[-1], HumanMessage):
        return END
    return "probe_turn"


def route_after_probe(state: TeachingState) -> str:
    if state.get("end_requested") or state.get("needs_report"):
        return "report_work"
    if state.get("phase") == "REVEAL":
        return "reveal_work"
    return END


def route_after_consolidate(state: TeachingState) -> str:
    if state.get("end_requested") or state.get("needs_report"):
        return "report_work"
    return END
