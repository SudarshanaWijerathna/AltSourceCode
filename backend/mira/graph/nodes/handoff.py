"""Handoff node: the traveller wants something that is not a catalogue tour.

Our FAQ and policy pages may still cover it (e.g. "airport transfers on their own ... priced by our
team on request"), so those are checked first and answered with sources. Either way the request is
recorded for the sales team and flagged; nothing is invented and no price is given.
"""

from __future__ import annotations

from langchain_core.messages import HumanMessage

from mira.graph.deps import Deps
from mira.graph.nodes.answer import grounded_answer, retrieve
from mira.graph.nodes.discovery import profile_summary, suggest_tours
from mira.graph.ui import source_list, specialist_handoff, tour_card
from mira.state import MiraState

SERVICE_PAGES = ("faq", "policy")


def make(deps: Deps):
    def run(state: MiraState) -> dict:
        requested = state["analysis"].get("unknown_tour")
        p = state["profile"]
        enquiry_id = deps.store.save_request(
            state["session_id"], "unknown_request",
            {"requested": requested, **profile_summary(p)}, state.get("trace_id"),
        )
        handoff_ui = specialist_handoff("Our team can check whether we can arrange this for you.")

        last = next((m.content for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), "")
        hits = retrieve(deps, f"{requested or ''} {last}", doc_types=SERVICE_PAGES)
        answer = grounded_answer(deps, state, hits)
        if answer:
            return {"facts": answer, "enquiry_id": enquiry_id, "needs_specialist": True,
                    "ui": [source_list(answer["sources"]), handoff_ui]}

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
            "ui": [*(tour_card(t) for t in related), handoff_ui],
        }

    return run
