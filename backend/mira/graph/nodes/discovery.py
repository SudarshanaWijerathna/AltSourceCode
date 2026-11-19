"""Asks for missing trip / traveller details - at most 3 questions (Req 1)."""

from mira.state import MiraState

MAX_QUESTIONS = 3


def run(state: MiraState) -> dict:
    # TODO: pick the single most useful missing slot; show something useful by question 3
    return {"questions_asked": state.get("questions_asked", 0) + 1}
