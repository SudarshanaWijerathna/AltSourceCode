"""Router: the LLM extracts intent and trip details; code merges them and picks the next node."""

from __future__ import annotations

from datetime import date

from langchain_core.messages import SystemMessage

from mira.data.rates import normalise_id
from mira.data.tours import TourInfo
from mira.graph.deps import Deps
from mira.graph.prompts import ROUTER_SYSTEM
from mira.state import MiraState, TripProfile, TurnAnalysis

HISTORY = 12  # messages of context passed to the LLMs

# Fields reset at the start of every turn.
TURN_RESET = {
    "facts": {}, "quote": None, "enquiry_id": None, "needs_specialist": False, "ui": [], "reply": "",
}


def merge_profile(old: TripProfile, a: TurnAnalysis, tours: dict[str, TourInfo]) -> TripProfile:
    """Deterministic merge: new values the traveller stated override what we knew."""
    p: TripProfile = dict(old)  # type: ignore[assignment]

    if a.tour_id:
        tid = normalise_id(a.tour_id)
        if tid in tours:  # never accept an id outside the published catalog
            p["tour_id"] = tid
    if a.start_date:
        try:
            p["start_date"] = date.fromisoformat(a.start_date).isoformat()
        except ValueError:
            pass
    if a.adults is not None and a.adults >= 0:
        p["adults"] = a.adults
    if a.child_ages is not None:
        ages = [x for x in a.child_ages if 0 <= x <= 17]
        p["child_ages"] = ages
        p["children_count"] = max(len(ages), a.children_count or 0)
    elif a.children_count is not None:
        p["children_count"] = a.children_count
        if len(p.get("child_ages", [])) != a.children_count:
            p["child_ages"] = []
    if a.destinations:
        p["destinations"] = sorted({d.lower() for d in a.destinations} | set(p.get("destinations", [])))
    if a.duration_days:
        p["duration_days"] = a.duration_days
    if a.trip_type:
        p["trip_type"] = a.trip_type
    if p.get("tour_id"):
        p["trip_type"] = "day_tour" if tours[p["tour_id"]].is_day_tour else "multi_day"

    if a.traveller_type:
        p["traveller_type"] = a.traveller_type
    elif "adults" in p:
        kids = p.get("children_count", 0)
        p["traveller_type"] = (
            "family" if kids else "solo" if p["adults"] == 1 else "couple" if p["adults"] == 2 else "group"
        )
    return p


def missing_slots(p: TripProfile) -> list[str]:
    missing = []
    if not p.get("tour_id"):
        missing.append("tour")
    if not p.get("adults"):
        missing.append("travellers")
    if not p.get("start_date"):
        missing.append("start_date")
    if p.get("children_count", 0) and len(p.get("child_ages", [])) != p["children_count"]:
        missing.append("child_ages")
    return missing


def make(deps: Deps):
    def run(state: MiraState) -> dict:
        system = ROUTER_SYSTEM.format(today=state["today"], catalog=deps.catalog_text)
        analysis = deps.analyze([SystemMessage(system), *state["messages"][-HISTORY:]])
        profile = merge_profile(state.get("profile", {}), analysis, deps.tours)
        return {**TURN_RESET, "analysis": analysis.model_dump(), "profile": profile}

    return run


def route(state: MiraState) -> str:
    a = state["analysis"]
    intent = a["intent"]
    if intent in ("greeting", "off_topic", "manipulation"):
        return "respond"
    if a.get("unknown_tour") and not a.get("tour_id"):
        return "handoff"
    if intent == "question":
        return "answer"
    return "discovery" if missing_slots(state["profile"]) else "pricing"
