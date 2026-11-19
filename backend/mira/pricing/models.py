"""Pricing contracts. Staff-only fields are separated from what travellers see."""

from datetime import date
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field


class QuoteRequest(BaseModel):
    tour_id: str
    start_date: date
    adults: int = Field(ge=1)
    child_ages: list[int] = []
    single_rooms: int = 0


class QuoteStatus(str, Enum):
    PRICED = "priced"
    MISSING_RATES = "missing_rates"
    EXPIRED_RATES = "expired_rates"


class LineItem(BaseModel):
    label: str
    amount_usd: Decimal


class TravellerQuote(BaseModel):
    """The only pricing shape that may reach the traveller or the LLM."""

    tour_id: str
    status: QuoteStatus
    price_usd: Decimal | None = None
    deposit_usd: Decimal | None = None
    lines: list[LineItem] = []


class StaffQuote(TravellerQuote):
    """Full breakdown stored with the enquiry - never sent to the traveller."""

    cost_usd: Decimal | None = None
    margin_pct: Decimal | None = None
    gross_profit_pct: Decimal | None = None
    reason: str | None = None  # why rates were missing/expired
