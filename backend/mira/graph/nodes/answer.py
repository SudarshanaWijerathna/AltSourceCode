"""Answer node: facts come from published content only, with the source shown (Req 4).

Interim version: grounds on the summary of the tour in focus. Full retrieval over tour,
destination and policy pages replaces this in the next step.
"""

from __future__ import annotations

from mira.graph.deps import Deps
from mira.graph.ui import tour_card
from mira.state import MiraState


def make(deps: Deps):
    def run(state: MiraState) -> dict:
        p = state["profile"]
        question = state["analysis"].get("question")
        tour_id = state["analysis"].get("tour_id") or p.get("tour_id")
        if tour_id and tour_id in deps.tours:
            t = deps.tours[tour_id]
            return {
                "facts": {
                    "kind": "no_content", "question": question,
                    "content": [{"source": t.source_path, "title": t.title, "duration": t.duration,
                                 "text": t.summary}],
                    "note": "Answer only if the content above answers the question; otherwise follow the instruction.",
                },
                "ui": [tour_card(t)],
            }
        return {"facts": {"kind": "no_content", "question": question}}

    return run
