"""Fixed generative-UI component catalog. Every payload is validated before reaching the browser."""

from typing import Annotated, Literal

from pydantic import BaseModel, Field, TypeAdapter, ValidationError


class TravellerPicker(BaseModel):
    """Adults / children counters. `final`: this answer completes the details needed for a price."""
    component: Literal["traveller_picker"]
    prompt: str
    final: bool = False


class TourCard(BaseModel):
    component: Literal["tour_card"]
    tour_id: str
    title: str
    duration: str
    summary: str
    source_path: str
    # "choose": a suggestion the traveller can pick. None: the tour is already chosen (no button).
    action: Literal["choose"] | None = None


class ItineraryDay(BaseModel):
    component: Literal["itinerary_day"]
    day: int = Field(ge=1)
    title: str
    description: str
    source_path: str


class DatePicker(BaseModel):
    """Start date input limited to dates we have rates for."""
    component: Literal["date_picker"]
    prompt: str
    min_date: str  # ISO date
    max_date: str  # ISO date
    final: bool = False


class ChildAgesPicker(BaseModel):
    component: Literal["child_ages_picker"]
    count: int = Field(ge=1, le=10)
    final: bool = False


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
    TravellerPicker | TourCard | ItineraryDay | PriceBreakdown | BookingForm | SpecialistHandoff | SourceList
    | DatePicker | ChildAgesPicker,
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
