"""Retrieval tests: published-only index, superseded statements, no teaser prices, ranking."""

import pytest

from mira.retrieval import get_index
from mira.retrieval.index import tokenize


@pytest.fixture(scope="module")
def ix():
    return get_index()


def ids(hits):
    return [h.chunk.id for h in hits]


def doc_ids(hits):
    return {h.chunk.doc_id for h in hits}


def test_drafts_are_never_indexed(ix):
    assert "T15" not in {c.doc_id for c in ix.chunks}  # Northern Sri Lanka Tour is a draft
    assert not any("jaffna" in c.text.lower() for c in ix.chunks)


def test_no_prices_from_tour_or_destination_pages(ix):
    for c in ix.chunks:
        if c.doc_type in ("tour", "destination"):
            assert "USD" not in c.text and "save 15%" not in c.text.lower(), c.id


def test_policy_fees_are_kept(ix):
    p02 = " ".join(c.text for c in ix.chunks if c.doc_id == "P02")
    assert "USD 50 admin fee" in p02


def test_kids_stay_free_offer_is_superseded_by_children_policy(ix):
    t07 = " ".join(c.text for c in ix.chunks if c.doc_id == "T07")
    assert "stay free" not in t07.lower()
    hits = ix.search("Do kids under 12 stay free on the Kandy Heritage Stay?", focus_doc="T07")
    assert "P03" in doc_ids(hits)


def test_old_cancellation_terms_are_superseded(ix):
    t04 = " ".join(c.text for c in ix.chunks if c.doc_id == "T04")
    assert "24 hours" not in t04
    hits = ix.search("What's the cancellation policy for the Galle Fort walking tour?", focus_doc="T04")
    assert "P02" in doc_ids(hits)
    assert all("24 hours" not in h.chunk.text for h in hits)


def test_supersession_pulls_in_policy_even_if_not_ranked(ix):
    # A query matching only the T07 intro (where the offer line was removed) still brings P03.
    hits = ix.search("unhurried colonial-era hotel by the lake", k=1, focus_doc="T07")
    assert ids(hits)[0] == "T07#intro"
    assert "P03" in doc_ids(hits)


@pytest.mark.parametrize("query, expected_doc", [
    ("Tell me about Polonnaruwa", "T09"),
    ("Can you do vegan meals?", "P04"),
    ("Which cards do you accept for payment?", "P01"),
    ("leopards safari Yala", "D06"),
    ("Tell me about Instafamous Sri Lanka", "T10"),
])
def test_relevant_page_is_retrieved(ix, query, expected_doc):
    assert expected_doc in doc_ids(ix.search(query))


def test_unrelated_query_returns_nothing(ix):
    assert ix.search("Do you have a tour to Jaffna?") == []
    assert ix.search("quantum chromodynamics lattice") == []


def test_tokenize_folds_plurals_and_drops_stopwords():
    assert tokenize("Do the leopards live in Yala?") == ["leopard", "live", "yala"]
