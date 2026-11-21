"""Builders for catalog UI components. Price components are built only from a stored quote."""

from __future__ import annotations

from mira.data.tours import TourInfo
from mira.pricing.models import TravellerQuote


def tour_card(t: TourInfo) -> dict:
    return {
        "component": "tour_card", "tour_id": t.id, "title": t.title, "duration": t.duration,
        "summary": t.summary, "source_path": t.source_path,
    }


def traveller_picker() -> dict:
    return {
        "component": "traveller_picker",
        "prompt": "Who is travelling?",
        "options": ["solo", "couple", "family", "group"],
    }


def price_breakdown(q: TravellerQuote, enquiry_id: str) -> dict:
    return {
        "component": "price_breakdown",
        "quote_id": enquiry_id,
        "price_usd": float(q.price_usd),
        "deposit_usd": float(q.deposit_usd),
        "balance_usd": float(q.balance_usd or 0),
        "balance_due": q.balance_due.isoformat() if q.balance_due else None,
    }


def itinerary_days(t: TourInfo) -> list[dict]:
    return [
        {"component": "itinerary_day", "day": n, "title": title, "description": text, "source_path": t.source_path}
        for n, title, text in t.days
    ]


def booking_form(enquiry_id: str) -> dict:
    return {"component": "booking_form", "quote_id": enquiry_id}


def source_list(sources: list[dict]) -> dict:
    return {"component": "source_list", "sources": sources}


def specialist_handoff(message: str) -> dict:
    return {"component": "specialist_handoff", "message": message}
