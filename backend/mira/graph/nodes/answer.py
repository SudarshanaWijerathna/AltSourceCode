"""Answer node: facts come from published content only, with the sources shown (Req 4).

1. Retrieve (code, BM25) over published tour, destination and policy chunks. Superseded tour
   statements are removed and the newer policy is retrieved instead (retrieval/rules.py).
2. The answer LLM answers from the numbered passages only and cites them.
3. Code checks the result: citations must point at retrieved passages, an answer without a
   citation is treated as not answered. Not answered -> Mira says so and offers an enquiry.
"""

from __future__ import annotations

import re

from langchain_core.messages import HumanMessage, SystemMessage

from mira.graph.deps import Deps
from mira.graph.nodes.router import HISTORY
from mira.graph.prompts import ANSWER_SYSTEM
from mira.graph.ui import source_list, tour_card
from mira.retrieval import Hit
from mira.state import MiraState
from mira.tracing import get_langfuse

MAX_PASSAGES = 6
_AMOUNT = re.compile(r"(?i)(?:usd|us\$|\$|lkr|rs\.?)\s*(\d[\d,]*)|(\d[\d,]*)\s*(?:usd|dollars?|lkr|rupees?)\b")


def amounts_in(text: str) -> set[str]:
    """Numbers written as money in a text ('USD 50' -> {'50'})."""
    return {(a or b).replace(",", "") for a, b in _AMOUNT.findall(text)}


def format_passages(hits: list[Hit]) -> str:
    blocks = []
    for n, h in enumerate(hits, start=1):
        c = h.chunk
        heading = f" > {c.heading}" if c.heading else ""
        blocks.append(f"[{n}] ({c.doc_type}) {c.title}{heading} — updated {c.last_updated}\n{c.text}")
    return "\n\n".join(blocks)


def _query(state: MiraState) -> str:
    question = state["analysis"].get("question")
    last = next((m.content for m in reversed(state["messages"]) if isinstance(m, HumanMessage)), "")
    return question or last


def make(deps: Deps):
    def run(state: MiraState) -> dict:
        p = state["profile"]
        focus = state["analysis"].get("tour_id") or p.get("tour_id")
        query = _query(state)
        if focus and focus in deps.tours:
            query = f"{query} {deps.tours[focus].title}"

        lf = get_langfuse()
        with lf.start_as_current_observation(
            as_type="retriever", name="retrieve-content", input={"query": query, "focus_tour": focus},
        ) as r:
            hits = deps.index.search(query, k=MAX_PASSAGES, focus_doc=focus)
            r.update(
                output=[{"id": h.chunk.id, "source": h.chunk.source_path, "score": h.score, "why": h.why,
                         "text": h.chunk.text[:400]} for h in hits],
                metadata={"superseded": sorted({s for h in hits for s in h.chunk.superseded})},
            )

        ui = [tour_card(deps.tours[focus])] if focus in deps.tours else []
        if not hits:
            return {"facts": {"kind": "no_content", "question": query}, "ui": ui}

        system = ANSWER_SYSTEM.format(today=state["today"], passages=format_passages(hits))
        result = deps.answer([SystemMessage(system), *state["messages"][-HISTORY:]])

        cited = sorted({n for n in result.citations if 1 <= n <= len(hits)})
        with lf.start_as_current_observation(
            as_type="guardrail", name="check-grounding",
            input={"answered": result.answered, "citations": result.citations, "passages": len(hits)},
        ) as g:
            grounded = result.answered and bool(result.answer.strip()) and bool(cited)
            g.update(output={"grounded": grounded, "valid_citations": cited},
                     level="DEFAULT" if grounded or not result.answered else "WARNING")

        if not grounded:
            return {"facts": {"kind": "no_content", "question": query}, "ui": ui}

        used = [hits[n - 1].chunk for n in cited]
        sources, seen = [], set()
        for c in used:
            if c.source_path not in seen:
                seen.add(c.source_path)
                sources.append({"title": c.title, "source_path": c.source_path})
        # Money figures may only be repeated from cited policy passages (e.g. an admin fee).
        allowed = sorted({a for c in used if c.doc_type in ("policy", "faq") for a in amounts_in(c.text)})
        return {
            "facts": {
                "kind": "answer",
                "final_text": result.answer.strip(),
                "sources": sources,
                "allowed_amounts": allowed,
            },
            "ui": [*ui, source_list(sources)],
        }

    return run
