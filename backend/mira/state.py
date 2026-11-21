"""Typed shared state passed between LangGraph nodes."""

from typing import Annotated, Literal, TypedDict

from langgraph.graph.message import add_messages

TripType = Literal["day_tour", "multi_day", "custom"]
TravellerType = Literal["solo", "couple", "family", "group"]


class Party(TypedDict, total=False):
    adults: int
    child_ages: list[int]  # rooms are derived by the pricing engine


class TripProfile(TypedDict, total=False):
    trip_type: TripType
    traveller_type: TravellerType
    party: Party
    start_date: str  # ISO date
    tour_id: str
    destinations: list[str]
    interests: list[str]


class Citation(TypedDict):
    source_id: str
    title: str
    path: str


class MiraState(TypedDict, total=False):
    messages: Annotated[list, add_messages]
    visitor_id: str
    profile: TripProfile
    questions_asked: int
    intent: Literal["discover", "answer", "quote", "enquire", "book", "off_topic"]
    retrieved: list[Citation]
    quote_id: str | None          # set only by the deterministic pricing node
    needs_specialist: bool        # missing / expired rates -> flag for staff
    ui: list[dict]                # validated component payloads for the client
