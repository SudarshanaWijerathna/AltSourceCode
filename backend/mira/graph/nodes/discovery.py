"""Discovery: asks for the single most useful missing detail, and shows something useful
(matching tours) by the third question at the latest (Req 1). Pure code, no LLM.

Each missing detail comes with an input card (travellers, start date, children's ages). The card
whose answer completes the details is marked `final` (its button reads "Get my price"). The chosen
tour's card is shown once, not repeated on every question."""

from __future__ import annotations

from datetime import timedelta

from mira.data.tours import TourInfo
from mira.graph.deps import Deps
from mira.graph.nodes.router import missing_slots
from mira.graph.ui import child_ages_picker, date_picker, tour_card, traveller_picker
from mira.pricing.engine import nights_from_duration
from mira.state import MiraState, TripProfile

MAX_QUESTIONS = 3

SLOT_TEXT = {
    "tour": "whether they want a day tour or a longer trip (if they already said, ask where instead)",
    "travellers": "how many adults and children are travelling",
    "start_date": "their preferred start date",
    "child_ages": "the age of each child (infants under 2 travel free)",
}


def suggest_tours(p: TripProfile, tours: dict[str, TourInfo], limit: int = 3) -> list[TourInfo]:
    """Closest published tours by destination overlap and duration.

    When the traveller named places, a suggestion must visit at least one of them: length and
    day-tour type only rank those tours, they never make an unrelated tour "related"."""
    wanted = {d.lower() for d in p.get("destinations", [])}
    days = p.get("duration_days")
    scored = []
    for t in tours.values():
        text = (t.title + " " + " ".join(t.destinations)).lower()
        hits = sum(1 for d in wanted if d in text)
        if wanted and not hits:
            continue
        score = 2 * hits
        if days:
            nights = nights_from_duration(t.duration) or 0
            score += 1 if abs((nights + 1) - days) <= 2 else 0
        if p.get("trip_type") == "day_tour" and t.is_day_tour:
            score += 1
        if score > 0:
            scored.append((score, t.id, t))
    return [t for _, _, t in sorted(scored, key=lambda x: (-x[0], x[1]))[:limit]]


def profile_summary(p: TripProfile) -> dict:
    keys = ("tour_id", "start_date", "adults", "children_count", "child_ages", "traveller_type",
            "trip_type", "destinations", "duration_days")
    return {k: p[k] for k in keys if p.get(k) not in (None, [], "")}


def date_range(deps: Deps, today: str, tour_id: str | None) -> tuple[str, str]:
    """Earliest and latest start dates we can price: today .. rates validity minus tour length."""
    s = deps.engine.rates.settings
    rate = deps.engine.rates.tours.get(tour_id or "")
    days = rate.days if rate else 1
    latest = (s.fx_valid_until - timedelta(days=days - 1)).isoformat() if s.fx_valid_until else "2099-12-31"
    return today, latest


def slot_inputs(deps: Deps, state: MiraState, p: TripProfile) -> list[dict]:
    """Input card for the next missing detail; `final` when its answer completes the details."""
    missing = missing_slots(p)
    if not missing:
        return []
    slot, final = missing[0], len(missing) == 1
    if slot == "travellers":
        return [traveller_picker(final=final)]
    if slot == "start_date":
        lo, hi = date_range(deps, state["today"], p.get("tour_id"))
        return [date_picker(lo, hi, final=final)]
    if slot == "child_ages" and p.get("children_count"):
        return [child_ages_picker(min(p["children_count"], 10), final=final)]
    return []


def make(deps: Deps):
    def run(state: MiraState) -> dict:
        p = state["profile"]
        asked = state.get("questions_asked", 0)
        slot = missing_slots(p)[0]
        ui: list[dict] = []

        if slot == "tour":
            suggestions = suggest_tours(p, deps.tours)
            custom = p.get("trip_type") == "custom"
            if suggestions and (custom or p.get("destinations") or asked + 1 >= MAX_QUESTIONS):
                facts = {
                    "kind": "suggest_tours",
                    "custom_request": custom,
                    "known": profile_summary(p),
                    "tours": [
                        {"id": t.id, "title": t.title, "duration": t.duration, "summary": t.summary,
                         "source": t.source_path}
                        for t in suggestions
                    ],
                }
                if custom:
                    enquiry_id = deps.store.save_request(
                        state["session_id"], "custom_request", profile_summary(p), state.get("trace_id")
                    )
                    facts["enquiry_saved"] = True
                else:
                    enquiry_id = None
                return {
                    "facts": facts,
                    "ui": [tour_card(t, action="choose") for t in suggestions],
                    "enquiry_id": enquiry_id,
                    "needs_specialist": custom,
                }

        shown = state.get("shown_tour")
        if p.get("tour_id") and p["tour_id"] != shown:
            ui.append(tour_card(deps.tours[p["tour_id"]]))  # chosen tour: shown once, no button
            shown = p["tour_id"]
        ui += slot_inputs(deps, state, p)
        facts = {"kind": "ask", "slot": SLOT_TEXT[slot], "known": profile_summary(p)}
        if p.get("tour_id"):
            t = deps.tours[p["tour_id"]]
            facts["tour"] = {"title": t.title, "duration": t.duration, "source": t.source_path}
        return {"facts": facts, "ui": ui, "questions_asked": asked + 1, "shown_tour": shown}

    return run
