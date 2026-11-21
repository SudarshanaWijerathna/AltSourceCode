"""Pricing contracts. Staff-only fields are kept apart from what travellers see."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from enum import Enum

from pydantic import BaseModel, Field, field_validator


class QuoteRequest(BaseModel):
    tour_id: str
    start_date: date
    adults: int = Field(ge=1, description="Travellers aged 12+ (children 12+ may also be listed in child_ages)")
    child_ages: list[int] = Field(default_factory=list, description="Ages of everyone under 18 not counted in adults")

    @field_validator("child_ages")
    @classmethod
    def _ages_in_range(cls, ages: list[int]) -> list[int]:
        if any(a < 0 or a > 17 for a in ages):
            raise ValueError("child ages must be between 0 and 17")
        return ages


class QuoteStatus(str, Enum):
    PRICED = "priced"
    MISSING_RATES = "missing_rates"        # a rate the price needs is not in the workbook
    EXPIRED_RATES = "expired_rates"        # rates exist but do not cover the travel dates
    AMBIGUOUS_RATES = "ambiguous_rates"    # conflicting rate rows cover the same night
    NOT_AVAILABLE = "not_available"        # draft / ended offer / content and rates disagree
    REFER_TO_SALES = "refer_to_sales"      # e.g. group larger than the private-tour maximum
    INVALID_REQUEST = "invalid_request"    # e.g. start date in the past

    @property
    def needs_specialist(self) -> bool:
        """True when staff must be flagged: Mira must not show a price and hands over."""
        return self not in (QuoteStatus.PRICED, QuoteStatus.INVALID_REQUEST)


class CostLine(BaseModel):
    category: str          # guide | vehicle | entrance | meals | hotel
    label: str
    amount_lkr: Decimal


class TravellerQuote(BaseModel):
    """The only pricing shape that may reach the traveller, the UI, or the LLM."""

    tour_id: str
    tour_name: str | None = None
    status: QuoteStatus
    start_date: date
    end_date: date | None = None
    adults: int
    children: int = 0
    infants: int = 0
    price_usd: Decimal | None = None
    deposit_usd: Decimal | None = None
    balance_usd: Decimal | None = None
    balance_due: date | None = None


class StaffQuote(TravellerQuote):
    """Full breakdown stored with the enquiry - never sent to the traveller."""

    vehicle: str | None = None
    cost_lines: list[CostLine] = []
    cost_lkr: Decimal | None = None
    cost_usd: Decimal | None = None
    sell_usd_unrounded: Decimal | None = None
    margin_pct: Decimal | None = None
    gross_profit_pct: Decimal | None = None
    reason: str | None = None
    rates_version: str | None = None
    quoted_on: date | None = None

    def traveller_view(self) -> TravellerQuote:
        return TravellerQuote.model_validate(
            self.model_dump(include=set(TravellerQuote.model_fields))
        )
