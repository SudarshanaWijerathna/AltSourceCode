"""Pricing unit tests.

Expected prices come from evals/eval_seed.jsonl and rates/sample_quotes.md in the dataset;
edge cases are hand-computed from the workbook's READ ME rules (working shown in comments).
"""

from dataclasses import replace
from datetime import date
from decimal import Decimal
from fractions import Fraction

import pytest

from mira.config import get_settings
from mira.pricing import build_engine
from mira.pricing.engine import MarginOverrides, PricingEngine, ceil_to, nights_from_duration
from mira.pricing.models import QuoteRequest, QuoteStatus, TravellerQuote

TODAY = date(2026, 11, 19)


@pytest.fixture(scope="module")
def engine() -> PricingEngine:
    return build_engine(get_settings())


def quote(engine, tour, start, adults, kids=(), today=TODAY):
    return engine.quote(
        QuoteRequest(tour_id=tour, start_date=start, adults=adults, child_ages=list(kids)), today
    )


def lines_by_category(q) -> dict[str, Decimal]:
    totals: dict[str, Decimal] = {}
    for line in q.cost_lines:
        totals[line.category] = totals.get(line.category, Decimal(0)) + line.amount_lkr
    return totals


# --------------------------------------------------------------------------- seed eval cases

@pytest.mark.parametrize(
    "case, tour, start, adults, kids, price, deposit",
    [
        ("S02", "T01", date(2027, 1, 10), 2, [], 315, 315),
        ("S03", "T09", date(2027, 4, 12), 2, [7, 10], 2965, 742),
        ("S13 turn 2", "T09", date(2027, 5, 3), 2, [], 2125, 532),
        ("S13 turn 3", "T09", date(2027, 5, 3), 4, [], 3640, 910),
        ("S15", "T05", date(2027, 3, 15), 2, [1], 275, 275),
    ],
)
def test_seed_prices(engine, case, tour, start, adults, kids, price, deposit):
    q = quote(engine, tour, start, adults, kids)
    assert q.status is QuoteStatus.PRICED, q.reason
    assert (q.price_usd, q.deposit_usd) == (Decimal(price), Decimal(deposit)), case


@pytest.mark.parametrize(
    "case, tour, start, adults, status",
    [
        ("S04 solo, H04 has no single rate", "T12", date(2027, 4, 10), 1, QuoteStatus.MISSING_RATES),
        ("S05 H07 rates expired", "T11", date(2027, 1, 20), 2, QuoteStatus.EXPIRED_RATES),
        ("S06 Instafamous has no rates", "T10", date(2027, 2, 10), 2, QuoteStatus.MISSING_RATES),
    ],
)
def test_seed_flag_no_price(engine, case, tour, start, adults, status):
    q = quote(engine, tour, start, adults)
    assert q.status is status, case
    assert q.status.needs_specialist
    assert q.price_usd is None and q.deposit_usd is None
    assert q.reason


# --------------------------------------------------------------------------- sample quotes (cost lines)

def test_q1041_cost_lines(engine):
    q = quote(engine, "T01", date(2027, 1, 10), 2)
    assert lines_by_category(q) == {
        "guide": 9000, "vehicle": 18000, "entrance": 33000, "meals": 6000,
    }
    assert q.cost_lkr == 66000 and q.vehicle == "Car"
    assert (q.price_usd, q.deposit_usd) == (315, 315)


def test_q1042_cost_lines_and_text_amount(engine):
    # H02 Shoulder double is stored as the text 'LKR 28,000' in the workbook.
    q = quote(engine, "T09", date(2027, 5, 3), 2)
    assert lines_by_category(q) == {
        "guide": 66500, "vehicle": 126000, "entrance": 76000, "meals": 63000, "hotel": 146000,
    }
    assert q.cost_lkr == 477500
    assert (q.price_usd, q.deposit_usd) == (2125, 532)


def test_q1043_sample_quote_omitted_extra_beds(engine):
    # Sales' Q-1043 shows hotels LKR 146,000 / USD 2,680 but forgot the children's extra beds
    # (READ ME rule 4). Correct: 146,000 + 2 beds x (4,500x2 + 6,000x2 + 5,500x2) = 210,000,
    # total 667,000 -> USD 2,965, which is what eval seed S03 expects.
    q = quote(engine, "T09", date(2027, 4, 12), 2, [7, 10])
    totals = lines_by_category(q)
    assert totals["vehicle"] == 182000 and q.vehicle == "Van"
    assert totals["entrance"] == 114000
    assert totals["meals"] == 94500
    assert totals["hotel"] == 210000
    assert q.price_usd == 2965


def test_q1044_starts_within_30_days_pays_in_full(engine):
    q = quote(engine, "T08", date(2026, 12, 1), 2)
    assert q.cost_lkr == 563000
    assert lines_by_category(q)["hotel"] == 187000
    assert (q.price_usd, q.deposit_usd, q.balance_usd) == (2505, 2505, 0)
    assert q.balance_due is None


# --------------------------------------------------------------------------- travellers & rooms

def test_infant_is_free_and_not_counted_for_vehicle(engine):
    with_baby = quote(engine, "T05", date(2027, 3, 15), 2, [1])
    without = quote(engine, "T05", date(2027, 3, 15), 2)
    assert with_baby.cost_lkr == without.cost_lkr
    assert with_baby.infants == 1 and with_baby.vehicle == "Car"


def test_child_aged_12_pays_as_adult(engine):
    teen = quote(engine, "T01", date(2027, 1, 10), 2, [12])
    three = quote(engine, "T01", date(2027, 1, 10), 3)
    assert teen.adults == 3 and teen.children == 0
    assert teen.price_usd == three.price_usd


def test_child_aged_2_is_a_child(engine):
    q = quote(engine, "T01", date(2027, 1, 10), 2, [2])
    assert q.children == 1 and q.infants == 0
    # entrance 2x16,500 + 8,250; meals 3,000 x (2 + 0.5)
    totals = lines_by_category(q)
    assert totals["entrance"] == 41250 and totals["meals"] == 7500


def test_odd_adult_takes_single_room(engine):
    # T07 Kandy Heritage Stay, 3 adults, May 2027 (H03 Shoulder: double 25,000, single 20,000)
    q = quote(engine, "T07", date(2027, 5, 10), 3)
    assert lines_by_category(q)["hotel"] == 2 * (25000 + 20000)


def test_vehicle_bands(engine):
    assert quote(engine, "T01", date(2027, 1, 10), 3).vehicle == "Car"
    assert quote(engine, "T01", date(2027, 1, 10), 4).vehicle == "Van"
    assert quote(engine, "T01", date(2027, 1, 10), 8).vehicle == "Van"
    assert quote(engine, "T01", date(2027, 1, 10), 9).vehicle == "Mini coach"


def test_twenty_travellers_priced_twenty_one_referred(engine):
    assert quote(engine, "T01", date(2027, 1, 10), 20).status is QuoteStatus.PRICED
    q = quote(engine, "T01", date(2027, 1, 10), 19, [5, 6])
    assert q.status is QuoteStatus.REFER_TO_SALES and q.price_usd is None


def test_infants_do_not_count_towards_group_limit(engine):
    assert quote(engine, "T01", date(2027, 1, 10), 20, [0]).status is QuoteStatus.PRICED


# --------------------------------------------------------------------------- dates & deposits

def test_multi_day_deposit_boundary_at_30_days(engine):
    # Exactly 30 days before start -> balance would be due today -> pay in full.
    at_30 = quote(engine, "T09", date(2026, 12, 19), 2)
    at_31 = quote(engine, "T09", date(2026, 12, 20), 2)
    assert at_30.deposit_usd == at_30.price_usd
    assert at_31.deposit_usd < at_31.price_usd
    assert at_31.balance_due == date(2026, 11, 20)


def test_deposit_is_25_percent_rounded_up(engine):
    q = quote(engine, "T09", date(2027, 5, 3), 2)  # 2125 x 25% = 531.25 -> 532
    assert q.deposit_usd == 532 and q.balance_usd == 2125 - 532


def test_day_tour_always_pays_in_full(engine):
    q = quote(engine, "T01", date(2027, 6, 1), 2)
    assert q.deposit_usd == q.price_usd


def test_start_date_in_past_is_invalid_not_flagged(engine):
    q = quote(engine, "T01", date(2026, 11, 18), 2)
    assert q.status is QuoteStatus.INVALID_REQUEST
    assert not q.status.needs_specialist and q.price_usd is None


def test_tour_ending_after_rate_validity_is_expired(engine):
    # T09 is 7 days: starts 28 Oct 2027, ends 3 Nov 2027, after the 31 Oct 2027 validity.
    q = quote(engine, "T09", date(2027, 10, 28), 2)
    assert q.status is QuoteStatus.EXPIRED_RATES


def test_today_is_a_parameter(engine):
    # Same request, different "today": within 30 days only for the later date.
    early = quote(engine, "T09", date(2027, 5, 3), 2, today=date(2026, 11, 19))
    late = quote(engine, "T09", date(2027, 5, 3), 2, today=date(2027, 4, 10))
    assert early.deposit_usd == 532 and late.deposit_usd == late.price_usd


# --------------------------------------------------------------------------- dirty workbook data

def test_hotel_contracted_in_usd_is_not_divided_by_fx(engine):
    # T13 (stored as 'T-13'), May 2027: guide 77,000 + car 126,000 + entrance 90,000
    # + meals 63,000 + H11 2x22,000 + H10 4x USD125x300 = 550,000 LKR -> USD 2,445 / 612.
    q = quote(engine, "T-13", date(2027, 5, 10), 2)
    assert q.tour_id == "T13"
    assert q.cost_lkr == 550000
    assert (q.price_usd, q.deposit_usd) == (2445, 612)


def test_hotel_date_stored_as_text_is_parsed(engine):
    # H08 Peak row has Valid from '15/12/2026' as text. T12 from 15 Dec 2026 puts nights 11-12
    # (25-26 Dec) at H08 Peak, double 52,000.
    q = quote(engine, "T12", date(2026, 12, 15), 2)
    assert q.status is QuoteStatus.PRICED, q.reason
    h08 = [l for l in q.cost_lines if " H08 " in l.label]
    assert [l.amount_lkr for l in h08] == [52000, 52000]


def test_overlapping_hotel_rates_are_ambiguous(engine):
    # H03 has two Peak rows covering Jan-Mar 2027 (25,000 and 34,000 'Revised per supplier email?').
    q = quote(engine, "T07", date(2027, 2, 10), 2)
    assert q.status is QuoteStatus.AMBIGUOUS_RATES and q.price_usd is None


def test_h03_outside_overlap_is_priced(engine):
    # Dec 2026 H03 Peak nights are only covered by the original row.
    assert quote(engine, "T07", date(2026, 12, 20), 2).status is QuoteStatus.PRICED


def test_loader_reports_known_data_issues(engine):
    text = "\n".join(engine.rates.warnings)
    for expected in ("'T-13' normalised", "Hotels!F8", "Hotels!D33", "H10): contracted in USD",
                     "H04): no single rate", "H03: rows 13 and 56 overlap", "H07: rates end"):
        assert expected in text


# --------------------------------------------------------------------------- not quotable

@pytest.mark.parametrize(
    "tour, status",
    [
        ("T06", QuoteStatus.NOT_AVAILABLE),   # page: 1 night / 2 days; rate sheet: day tour, 0 nights
        ("T14", QuoteStatus.NOT_AVAILABLE),   # Winter 2023/24 offer has ended
        ("T15", QuoteStatus.NOT_AVAILABLE),   # draft page, 'not launched yet'
        ("T16", QuoteStatus.MISSING_RATES),   # published page, no rate row
        ("T99", QuoteStatus.NOT_AVAILABLE),   # no such tour
    ],
)
def test_tours_that_must_not_be_quoted(engine, tour, status):
    q = quote(engine, tour, date(2027, 2, 10), 2)
    assert q.status is status
    assert q.price_usd is None and q.status.needs_specialist


# --------------------------------------------------------------------------- margins & rounding

def test_margin_override_changes_price(engine):
    custom = PricingEngine(engine.rates, engine.content, MarginOverrides(day=Fraction("0.35")))
    q = quote(custom, "T01", date(2027, 1, 10), 2)
    # 220 USD cost / 0.65 = 338.46 -> 340
    assert q.price_usd == 340 and q.margin_pct == Decimal("35.0")


def test_gross_profit_is_on_selling_price(engine):
    q = quote(engine, "T01", date(2027, 1, 10), 2)
    # (315 - 220) / 315 = 30.16%
    assert q.cost_usd == Decimal("220.00") and q.gross_profit_pct == Decimal("30.2")


@pytest.mark.parametrize(
    "value, expected",
    [(Fraction(31429, 100), 315), (Fraction(315), 315), (Fraction(3151, 10), 320), (Fraction(1, 100), 5)],
)
def test_ceil_to_five(value, expected):
    assert ceil_to(value, 5) == expected


def test_settings_loaded_from_workbook(engine):
    s = engine.rates.settings
    assert s.fx_lkr_per_usd == 300 and s.fx_valid_until == date(2027, 10, 31)
    assert (s.margin_day, s.margin_multi, s.deposit_multi) == (
        Fraction("0.3"), Fraction("0.25"), Fraction("0.25"),
    )
    assert (s.full_payment_within_days, s.max_group_size, s.round_to_usd) == (30, 20, 5)


@pytest.mark.parametrize(
    "text, nights", [("6 nights / 7 days", 6), ("1 night / 2 days", 1), ("1 day", 0), ("Half day", 0)]
)
def test_nights_from_duration(text, nights):
    assert nights_from_duration(text) == nights


# --------------------------------------------------------------------------- privacy

def test_traveller_view_hides_costs_and_margins(engine):
    q = quote(engine, "T09", date(2027, 5, 3), 2)
    view = q.traveller_view()
    assert isinstance(view, TravellerQuote)
    dumped = view.model_dump()
    for staff_field in ("cost_lines", "cost_lkr", "cost_usd", "margin_pct", "gross_profit_pct",
                        "reason", "sell_usd_unrounded", "vehicle"):
        assert staff_field not in dumped
    assert dumped["price_usd"] == 2125 and dumped["deposit_usd"] == 532


def test_request_rejects_bad_ages():
    with pytest.raises(ValueError):
        QuoteRequest(tour_id="T01", start_date=TODAY, adults=2, child_ages=[-1])
    with pytest.raises(ValueError):
        QuoteRequest(tour_id="T01", start_date=TODAY, adults=0)


def test_rate_book_is_not_mutated_by_quoting(engine):
    before = replace(engine.rates.settings)
    quote(engine, "T09", date(2027, 5, 3), 2)
    assert engine.rates.settings == before
