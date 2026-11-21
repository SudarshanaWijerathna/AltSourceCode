"""Handoff node: the traveller wants something we don't sell. Never invent it; record the
request for the sales team and point to the closest real tours."""

from __future__ import annotations

from mira.graph.deps import Deps
from mira.graph.nodes.discovery import profile_summary, suggest_tours
from mira.graph.ui import specialist_handoff, tour_card
from mira.state import MiraState


def make(deps: Deps):
    def run(state: MiraState) -> dict:
        requested = state["analysis"].get("unknown_tour")
        p = state["profile"]
        enquiry_id = deps.store.save_request(
            state["session_id"], "unknown_request",
            {"requested": requested, **profile_summary(p)}, state.get("trace_id"),
        )
        related = suggest_tours(p, deps.tours, limit=2)
        return {
            "facts": {
                "kind": "unknown_tour",
                "requested": requested,
                "related_tours": [{"id": t.id, "title": t.title, "duration": t.duration} for t in related],
                "enquiry_saved": True,
            },
            "enquiry_id": enquiry_id,
            "needs_specialist": True,
            "ui": [tour_card(t) for t in related]
            + [specialist_handoff("Our team can check whether we can arrange this for you.")],
        }

    return run
