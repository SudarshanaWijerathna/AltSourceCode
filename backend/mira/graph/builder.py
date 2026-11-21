"""LangGraph wiring.

    START -> router --(code decides)--> discovery | answer | pricing | handoff | respond
                                             \\        |        |        /
                                              ---------> respond -> END

Only router and respond call the LLM. discovery, pricing and handoff are deterministic code.
"""

from __future__ import annotations

from langgraph.checkpoint.base import BaseCheckpointSaver
from langgraph.checkpoint.memory import InMemorySaver
from langgraph.graph import END, START, StateGraph

from mira.graph.deps import Deps
from mira.graph.nodes import answer, discovery, handoff, pricing, respond, router
from mira.state import MiraState

ROUTES = ("discovery", "answer", "pricing", "handoff", "respond")


def build_graph(deps: Deps, checkpointer: BaseCheckpointSaver | None = None):
    g = StateGraph(MiraState)
    g.add_node("router", router.make(deps))
    g.add_node("discovery", discovery.make(deps))
    g.add_node("answer", answer.make(deps))
    g.add_node("pricing", pricing.make(deps))
    g.add_node("handoff", handoff.make(deps))
    g.add_node("respond", respond.make(deps))

    g.add_edge(START, "router")
    g.add_conditional_edges("router", router.route, {r: r for r in ROUTES})
    for node in ("discovery", "answer", "pricing", "handoff"):
        g.add_edge(node, "respond")
    g.add_edge("respond", END)
    return g.compile(checkpointer=checkpointer or InMemorySaver())
