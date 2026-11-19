"""Chooses catalog components for the reply and validates them before they leave the server."""

from mira.state import MiraState
from mira.ui.catalog import validate_components


def run(state: MiraState) -> dict:
    return {"ui": validate_components(state.get("ui", []))}
