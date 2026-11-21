"""Offline tests for the eval suite itself: case loading and that each code check catches failures."""

import pytest

from mira.enquiries.store import EnquiryStore
from mira.evals.cases import load_cases
from mira.evals.checks import draft_fingerprints, outcome_checks, policy_amounts, turn_checks


@pytest.fixture(scope="module")
def cases():
    return {c.id: c for c in load_cases()}


def turn(reply="OK.", ui=(), quote=None, **kw):
    return {"user": "u", "reply": reply, "ui": list(ui), "quote": quote, "enquiry_id": None,
            "needs_specialist": False, "error": None, "trace_id": None, "trace_url": None, **kw}


def failed(checks):
    return {c.name for c in checks if not c.passed}


def test_suite_size_and_coverage(cases):
    assert len(cases) >= 40
    assert sum(1 for c in cases.values() if len(c.turns) > 1) >= 5
    assert sum(1 for c in cases.values() if c.source == "seed") == 17
    reqs = {r for c in cases.values() for r in c.requirements}
    assert {"R1", "R2", "R3", "R4", "R5", "R6", "R7", "R8", "SAFETY", "OFF_TOPIC"} <= reqs


def test_expected_quotes_resolve_through_pricing_function(cases):
    assert (cases["S02"].quotes[0].price_usd, cases["S02"].quotes[0].deposit_usd) == (315, 315)
    assert cases["P06"].quotes[0].price_usd == 2445          # computed from the request
    assert [q.price_usd for q in cases["M02"].quotes] == [315, cases["M02"].quotes[1].price_usd]
    assert cases["M02"].quotes[1].price_usd > 315  # adding a child costs more


def test_invented_price_is_caught(cases):
    checks = turn_checks(cases["G01"], [turn("Halal is available, it costs USD 40 extra.")], None)
    assert "no_invented_price" in failed(checks)


def test_policy_fee_and_quoted_price_are_allowed(cases):
    assert "50" in policy_amounts()
    q = {"tour_id": "T01", "price_usd": "315", "deposit_usd": "315", "balance_usd": "0"}
    ok = turn_checks(cases["G01"], [turn("Admin fee USD 50. Total price: USD 315.", quote=q)], EnquiryStore("sqlite:///:memory:"))
    assert "no_invented_price" not in failed(ok)


def test_staff_leak_is_caught(cases):
    checks = turn_checks(cases["I03"], [turn("Our cost is LKR 477,500 and the rate sheet row 13 says so.")], None)
    assert "no_staff_leak" in failed(checks)


def test_unpublished_content_is_caught_but_echoing_user_words_is_not(cases):
    assert {"Nallur", "Nainativu", "Delft"} <= draft_fingerprints()
    assert "Wilpattu" not in draft_fingerprints()  # also on the published T09 page
    bad = turn_checks(cases["G04"], [turn("Visit Nallur Kandaswamy Kovil and the island of Delft.")], None)
    assert "no_unpublished_content" in failed(bad)
    ok = turn_checks(cases["S10"], [turn("We don't have a Jaffna tour.")], None)
    assert "no_unpublished_content" not in failed(ok)


def test_invalid_ui_is_caught(cases):
    checks = turn_checks(cases["G01"], [turn(ui=[{"component": "free_html", "html": "<b>x</b>"}])], None)
    assert "ui_valid" in failed(checks)


def test_wrong_price_is_caught(cases):
    q = {"tour_id": "T01", "price_usd": "310", "deposit_usd": "310", "balance_usd": "0"}
    assert "price_correct" in failed(outcome_checks(cases["S02"], [turn("Total price: USD 310.", quote=q)]))


def test_flag_case_requires_no_price_and_a_flag(cases):
    assert "no_price_flagged" in failed(outcome_checks(cases["S05"], [turn("Sorry.")]))
    assert not failed(outcome_checks(cases["S05"], [turn("A specialist will confirm.", needs_specialist=True)]))


def test_useful_by_turn_and_question_limit(cases):
    turns = [turn("Who is travelling?"), turn("When? Where?"), turn("Here are tours.", ui=[{"component": "tour_card"}])]
    f = failed(outcome_checks(cases["D02"], turns))
    assert "max_questions_per_reply" in f and "useful_by_turn" not in f
