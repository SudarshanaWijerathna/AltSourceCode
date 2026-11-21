"""Dependencies injected into graph nodes (real Gemini models in the app, fakes in tests)."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from mira.data.tours import TourInfo
from mira.enquiries.store import EnquiryStore
from mira.pricing.engine import PricingEngine
from mira.retrieval import ContentIndex
from mira.state import GroundedAnswer, TurnAnalysis

Analyzer = Callable[[list], TurnAnalysis]   # messages -> structured analysis (router LLM)
Writer = Callable[[list], str]               # messages -> reply text (responder LLM)
Answerer = Callable[[list], GroundedAnswer]  # messages -> grounded answer (answer LLM)


@dataclass
class Deps:
    analyze: Analyzer
    write: Writer
    engine: PricingEngine
    store: EnquiryStore
    tours: dict[str, TourInfo]
    catalog_text: str
    answer: Answerer
    index: ContentIndex
