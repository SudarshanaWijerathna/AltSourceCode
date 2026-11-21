"""Load eval cases: the dataset's seed cases (read in place, unchanged) plus ours.

Seed cases carry literal expected prices. Our pricing cases state the request instead, and the
expected price is the pricing function's result for that request (the function is unit-tested
against the seed cases and the sales team's sample quotes).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date

from mira.config import REPO_ROOT, get_settings
from mira.pricing import get_engine
from mira.pricing.models import QuoteRequest, QuoteStatus

SEED_REQUIREMENTS = {
    "discovery": ["R1"],
    "pricing": ["R5", "R7"],
    "rates": ["R6"],
    "grounding": ["R4"],
    "safety": ["SAFETY"],
    "multi_turn": ["R1", "R5"],
    "off_topic": ["OFF_TOPIC"],
}

REQUIREMENT_NAMES = {
    "R1": "Discover the trip",
    "R2": "Remember returning visitors",
    "R3": "Generate the interface",
    "R4": "Answer from content only",
    "R5": "Quote correct prices",
    "R6": "Handle missing or expired rates",
    "R7": "Save private enquiries",
    "R8": "Approve AI-written content",
    "SAFETY": "Prompt injection & manipulation",
    "OFF_TOPIC": "Off-topic requests",
}


@dataclass
class ExpectedQuote:
    tour: str
    price_usd: int
    deposit_usd: int


@dataclass
class Case:
    id: str
    source: str                      # seed | mira
    category: str
    requirements: list[str]
    turns: list[str]
    expected: dict
    checks: dict = field(default_factory=dict)
    note: str = ""
    quotes: list[ExpectedQuote] = field(default_factory=list)   # resolved expected quotes
    sessions: list[list[str]] | None = None   # several sessions by the same visitor (Req 2)

    @property
    def behaviour(self) -> str | None:
        return self.expected.get("behaviour")


def _resolve_quote(spec: dict, today: date) -> ExpectedQuote:
    if "price_usd" in spec:
        return ExpectedQuote(spec["tour"], int(spec["price_usd"]), int(spec["deposit_usd"]))
    r = spec["request"]
    q = get_engine().quote(
        QuoteRequest(tour_id=spec["tour"], start_date=date.fromisoformat(r["start_date"]),
                     adults=r["adults"], child_ages=r.get("child_ages", [])),
        today,
    )
    if q.status is not QuoteStatus.PRICED:
        raise ValueError(f"case expects a quote for {spec} but the pricing function says {q.status}: {q.reason}")
    return ExpectedQuote(spec["tour"], int(q.price_usd), int(q.deposit_usd))


def _read_jsonl(path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_cases() -> list[Case]:
    s = get_settings()
    today = s.mira_today
    cases: list[Case] = []
    for raw in _read_jsonl(s.eval_seed):
        cases.append(Case(
            id=raw["id"], source="seed", category=raw["category"],
            requirements=SEED_REQUIREMENTS.get(raw["category"], [raw["category"].upper()]),
            turns=raw["turns"], expected=raw["expected"],
        ))
    for path in sorted((REPO_ROOT / "evals" / "cases").glob("*.jsonl")):
        for raw in _read_jsonl(path):
            sessions = raw.get("sessions")
            cases.append(Case(
                id=raw["id"], source="mira", category=raw["category"], requirements=raw["requirements"],
                turns=[t for s in sessions for t in s] if sessions else raw["turns"],
                expected=raw["expected"], checks=raw.get("checks", {}), note=raw.get("note", ""),
                sessions=sessions,
            ))
    ids = [c.id for c in cases]
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate case ids")
    for c in cases:
        t = c.expected["type"]
        if t == "quote":
            c.quotes = [_resolve_quote(c.expected, today)]
        elif t == "quote_sequence":
            c.quotes = [_resolve_quote(q, today) for q in c.expected["quotes"]]
    return cases
