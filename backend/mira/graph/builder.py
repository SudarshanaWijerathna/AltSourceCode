"""LangGraph wiring: router -> (discovery | answer | pricing) -> ui composer."""

from langgraph.graph import END, START, StateGraph

from mira.graph.nodes import answer, discovery, pricing, router, ui_composer
from mira.state import MiraState


def build_graph():
    g = StateGraph(MiraState)
    g.add_node("router", router.run)
    g.add_node("discovery", discovery.run)
    g.add_node("answer", answer.run)
    g.add_node("pricing", pricing.run)
    g.add_node("ui_composer", ui_composer.run)

    g.add_edge(START, "router")
    g.add_conditional_edges(
        "router",
        router.route,
        {"discover": "discovery", "answer": "answer", "quote": "pricing"},
    )
    for node in ("discovery", "answer", "pricing"):
        g.add_edge(node, "ui_composer")
    g.add_edge("ui_composer", END)
    return g.compile()
