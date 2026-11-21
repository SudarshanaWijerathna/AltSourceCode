"""Dependencies injected into graph nodes (real Gemini models in the app, fakes in tests)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from mira.data.tours import TourInfo
from mira.enquiries.store import EnquiryStore
from mira.pricing.engine import PricingEngine
from mira.state import TurnAnalysis

Analyzer = Callable[[list], TurnAnalysis]   # messages -> structured analysis (router LLM)
Writer = Callable[[list], str]               # messages -> reply text (responder LLM)


@dataclass
class Deps:
    analyze: Analyzer
    write: Writer
    engine: PricingEngine
    store: EnquiryStore
    tours: dict[str, TourInfo]
    catalog_text: str
