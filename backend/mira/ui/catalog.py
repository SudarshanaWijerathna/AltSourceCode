"""Fixed generative-UI component catalog. Every payload is validated before reaching the browser."""

from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field, TypeAdapter


class TravellerPicker(BaseModel):
    component: Literal["traveller_picker"]
    prompt: str
    options: list[Literal["solo", "couple", "family", "group"]]


class TourCard(BaseModel):
    component: Literal["tour_card"]
    tour_id: str
    title: str
    duration: str
    summary: str
    source_path: str


class ItineraryDay(BaseModel):
    component: Literal["itinerary_day"]
    day: int = Field(ge=1)
    title: str
    description: str
    source_path: str


class PriceBreakdown(BaseModel):
    component: Literal["price_breakdown"]
    quote_id: str  # rendered from the stored quote, never from model text
    price_usd: float
    deposit_usd: float
    lines: list[dict] = []


class BookingForm(BaseModel):
    component: Literal["booking_form"]
    quote_id: str


class SpecialistHandoff(BaseModel):
    component: Literal["specialist_handoff"]
    message: str


Component = Annotated[
    Union[TravellerPicker, TourCard, ItineraryDay, PriceBreakdown, BookingForm, SpecialistHandoff],
    Field(discriminator="component"),
]
_adapter = TypeAdapter(list[Component])


def validate_components(payload: list[dict]) -> list[dict]:
    """Raises pydantic.ValidationError if any component is not in the catalog."""
    return [c.model_dump() for c in _adapter.validate_python(payload)]
