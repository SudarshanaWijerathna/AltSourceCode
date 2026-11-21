"""Pricing node: deterministic. Builds the request from the profile, calls the pricing engine,
saves the private enquiry with its trace id, and exposes only the traveller view (Req 5, 6, 7)."""

from __future__ import annotations

from datetime import date

from mira.graph.deps import Deps
from mira.graph.nodes.discovery import profile_summary, slot_inputs
from mira.graph.ui import (
    booking_form,
    itinerary_days,
    price_breakdown,
    source_list,
    specialist_handoff,
    tour_card,
)
from mira.pricing.models import QuoteRequest, QuoteStatus
from mira.state import MiraState
from mira.tracing import get_langfuse

HANDOFF_MESSAGE = "A travel specialist will check this trip and confirm your price."


def make(deps: Deps):
    def run(state: MiraState) -> dict:
        p = state["profile"]
        today = date.fromisoformat(state["today"])
        req = QuoteRequest(
            tour_id=p["tour_id"],
            start_date=date.fromisoformat(p["start_date"]),
            adults=p["adults"],
            child_ages=p.get("child_ages", []),
        )
        with get_langfuse().start_as_current_observation(
            as_type="tool", name="calculate-quote", input=req.model_dump(mode="json"),
        ) as obs:
            quote = deps.engine.quote(req, today)
            obs.update(
                output=quote.traveller_view().model_dump(mode="json"),
                metadata={
                    "status": quote.status.value,
                    "staff_reason": quote.reason,
                    "cost_lines": [c.model_dump(mode="json") for c in quote.cost_lines],
                    "cost_usd": str(quote.cost_usd) if quote.cost_usd is not None else None,
                    "margin_pct": str(quote.margin_pct) if quote.margin_pct is not None else None,
                    "gross_profit_pct": str(quote.gross_profit_pct) if quote.gross_profit_pct is not None else None,
                    "rates_version": quote.rates_version,
                    "today": state["today"],
                },
                level="WARNING" if quote.status.needs_specialist else "DEFAULT",
            )

        tour = deps.tours[quote.tour_id]
        view = quote.traveller_view()
        base_facts = {
            "tour": {"title": tour.title, "duration": tour.duration, "summary": tour.summary,
                     "source": tour.source_path},
            "known": profile_summary(p),
        }
        if state["analysis"].get("intent") == "manipulation":
            base_facts["also"] = ("First say in one short sentence that prices, margins and rules are fixed "
                                  "and can't be changed by request.")

        if quote.status is QuoteStatus.INVALID_REQUEST:
            profile = {k: v for k, v in p.items() if k != "start_date"}
            return {"facts": {**base_facts, "kind": "invalid_date"}, "profile": profile,
                    "ui": slot_inputs(deps, state, profile)}

        enquiry_id = deps.store.save_quote(quote, state["session_id"], state.get("trace_id"))
        if quote.status is QuoteStatus.PRICED:
            return {
                "facts": {
                    **base_facts, "kind": "quote",
                    "dates": {"start": view.start_date.isoformat(),
                              "end": view.end_date.isoformat() if view.end_date else None},
                    "party": {"adults": view.adults, "children": view.children, "infants": view.infants},
                },
                "quote": view.model_dump(mode="json"),
                "enquiry_id": enquiry_id,
                "shown_tour": tour.id,
                "ui": [tour_card(tour), *itinerary_days(tour), price_breakdown(view, enquiry_id),
                       booking_form(enquiry_id)],
            }
        sources = [{"title": tour.title, "source_path": tour.source_path}]
        return {
            "facts": {**base_facts, "kind": "handoff", "sources": sources},
            "enquiry_id": enquiry_id,
            "needs_specialist": True,
            "ui": [tour_card(tour), specialist_handoff(HANDOFF_MESSAGE), source_list(sources)],
        }

    return run
