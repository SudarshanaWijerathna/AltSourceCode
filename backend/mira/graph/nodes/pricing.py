"""Deterministic pricing node: calls mira.pricing - the LLM never does arithmetic (Req 5, 6)."""

from mira.state import MiraState


def run(state: MiraState) -> dict:
    # TODO: build QuoteRequest from state["profile"], call pricing.engine.quote(),
    #       persist enquiry with trace id, or set needs_specialist on missing/expired rates
    return {"quote_id": None, "needs_specialist": False}
