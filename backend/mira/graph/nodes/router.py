"""Classifies the turn's intent and fills the trip profile (LLM, structured output)."""

from mira.state import MiraState


def run(state: MiraState) -> dict:
    # TODO: LLM structured extraction of intent + profile slots
    return {"intent": state.get("intent", "discover")}


def route(state: MiraState) -> str:
    intent = state.get("intent", "discover")
    return intent if intent in {"discover", "answer", "quote"} else "answer"
