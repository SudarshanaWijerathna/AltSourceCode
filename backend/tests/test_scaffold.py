"""Smoke tests for the scaffold: config, dataset loading, UI catalog, graph compiles."""

import pytest
from pydantic import ValidationError

from mira.config import get_settings
from mira.data.content import load_content
from mira.graph.builder import build_graph
from mira.ui.catalog import validate_components


def test_today_is_configurable_default():
    assert get_settings().mira_today.isoformat() == "2026-11-19"


def test_dataset_present():
    s = get_settings()
    assert s.rate_workbook.exists()
    assert s.eval_seed.exists()


def test_content_loads():
    docs = load_content(get_settings().content_dir)
    assert len([d for d in docs if d.type == "tour"]) >= 16


def test_catalog_rejects_unknown_component():
    with pytest.raises(ValidationError):
        validate_components([{"component": "free_html", "html": "<b>hi</b>"}])


def test_graph_compiles():
    assert build_graph() is not None
