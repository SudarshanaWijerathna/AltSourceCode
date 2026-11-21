"""Pricing: deterministic quotes from the rate workbook. See engine.py for the rules."""

from fractions import Fraction
from functools import lru_cache

from mira.config import Settings, get_settings
from mira.data.content import load_all_content
from mira.data.rates import load_ratebook
from mira.pricing.engine import (
    MarginOverrides,
    PricingEngine,
    TourContentInfo,
    nights_from_duration,
)


def build_engine(settings: Settings) -> PricingEngine:
    rates = load_ratebook(settings.rate_workbook)
    content = {
        doc.id: TourContentInfo(status=doc.status, nights=nights_from_duration(doc.meta.get("duration")))
        for doc in load_all_content(settings)
        if doc.type == "tour"
    }
    margins = MarginOverrides(
        day=Fraction(str(settings.mira_margin_day_tour)) if settings.mira_margin_day_tour is not None else None,
        multi=Fraction(str(settings.mira_margin_multi_day)) if settings.mira_margin_multi_day is not None else None,
    )
    return PricingEngine(rates, content, margins)


@lru_cache
def get_engine() -> PricingEngine:
    return build_engine(get_settings())
