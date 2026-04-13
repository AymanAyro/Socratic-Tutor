"""Compile the Stage 2 LangGraph teaching graph."""

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.graph import END, START, StateGraph

from Engine.edges import route_after_consolidate, route_after_probe, route_ingress
from Engine.nodes import (
    consolidate_turn,
    probe_turn,
    reflect_consolidate,
    report_work,
    reveal_work,
)
from Engine.state import TeachingState


def build_teaching_graph(checkpointer: BaseCheckpointSaver):
    g = StateGraph(TeachingState)
    g.add_node("probe_turn", probe_turn)
    g.add_node("reveal_work", reveal_work)
    g.add_node("consolidate_turn", consolidate_turn)
    g.add_node("reflect_consolidate", reflect_consolidate)
    g.add_node("report_work", report_work)

    g.add_conditional_edges(
        START,
        route_ingress,
        {
            "probe_turn": "probe_turn",
            "consolidate_turn": "consolidate_turn",
            "report_work": "report_work",
            END: END,
        },
    )
    g.add_conditional_edges(
        "probe_turn",
        route_after_probe,
        {
            "reveal_work": "reveal_work",
            "report_work": "report_work",
            END: END,
        },
    )
    g.add_edge("reveal_work", END)
    g.add_conditional_edges(
        "consolidate_turn",
        route_after_consolidate,
        {
            "report_work": "report_work",
            END: END,
        },
    )
    g.add_edge("report_work", END)
    g.add_edge("reflect_consolidate", END)

    return g.compile(checkpointer=checkpointer)
