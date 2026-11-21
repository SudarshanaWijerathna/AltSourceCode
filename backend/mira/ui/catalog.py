"""Fixed generative-UI component catalog. Every payload is validated before reaching the browser."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter, ValidationError


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
    priced: bool = False  # True when the same reply already shows this tour's price


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
    balance_usd: float = 0
    balance_due: str | None = None  # ISO date


class BookingForm(BaseModel):
    component: Literal["booking_form"]
    quote_id: str


class Source(BaseModel):
    title: str
    source_path: str


class SourceList(BaseModel):
    component: Literal["source_list"]
    sources: list[Source] = Field(min_length=1)


class SpecialistHandoff(BaseModel):
    component: Literal["specialist_handoff"]
    message: str


Component = Annotated[
    TravellerPicker | TourCard | ItineraryDay | PriceBreakdown | BookingForm | SpecialistHandoff | SourceList,
    Field(discriminator="component"),
]
_adapter = TypeAdapter(list[Component])


_one = TypeAdapter(Component)


def validate_components(payload: list[dict]) -> list[dict]:
    """Raises pydantic.ValidationError if any component is not in the catalog."""
    return [c.model_dump() for c in _adapter.validate_python(payload)]


def validate_each(payload: list[dict]) -> tuple[list[dict], list[str]]:
    """Keep valid components, drop invalid ones. Returns (valid, error descriptions)."""
    valid, errors = [], []
    for i, item in enumerate(payload):
        try:
            valid.append(_one.validate_python(item).model_dump())
        except ValidationError as e:
            name = item.get("component", "?") if isinstance(item, dict) else type(item).__name__
            errors.append(f"#{i} {name}: {e.errors()[0]['msg']}")
    return valid, errors
