"""Deterministic pricing function implementing the rules on the workbook's READ ME tab.

All arithmetic uses exact fractions; rounding happens only where the rules say so.
The LLM never computes prices: it calls `PricingEngine.quote()` and shows the result.

  1. Cost (LKR) = guide/day x days + vehicle/day x days + entrance per person
                  + meals per person per day x days + hotel rooms for each night
  2. Vehicle by group size (adults + children 2-11; infants not counted)
  3. Rooms: 2 adults per double, odd adult in a single, 1 extra bed per child 2-11
  4. Children 2-11: child entrance, 50% meals. Infants < 2 free. 12+ pay as adults
  5. Hotel rate = the row covering that night (night 1 = start date)
  6. USD = LKR / FX; Sell = Cost / (1 - margin); round total UP to next USD 5
  7. Deposit: day tours in full; multi-day 25% rounded up to whole USD, or in full
     if the tour starts within 30 days
  8. More than 20 travellers, or any rate not in the workbook -> hand over, never guess
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass
from datetime import date, timedelta
from decimal import ROUND_HALF_UP, Decimal
from fractions import Fraction

from mira.data.rates import HotelRate, RateBook, TourRate, normalise_id
from mira.pricing.models import CostLine, QuoteRequest, QuoteStatus, StaffQuote
from mira.pricing.rules import NOT_QUOTABLE


@dataclass(frozen=True)
class TourContentInfo:
    """What the pricing engine needs to know about a tour's published page."""

    status: str           # "published" | "draft"
    nights: int | None    # parsed from the page's duration, None if unknown


@dataclass(frozen=True)
class MarginOverrides:
    day: Fraction | None = None
    multi: Fraction | None = None


class _NoPrice(Exception):
    def __init__(self, status: QuoteStatus, reason: str):
        super().__init__(reason)
        self.status = status
        self.reason = reason


def ceil_to(value: Fraction, step: int) -> Fraction:
    """Round up to the next multiple of `step` (exact multiples stay as they are)."""
    return Fraction(math.ceil(value / step) * step)


def _dec(value: Fraction, places: str = "0.01") -> Decimal:
    return (Decimal(value.numerator) / Decimal(value.denominator)).quantize(
        Decimal(places), rounding=ROUND_HALF_UP
    )


def _money(value: Fraction) -> Decimal:
    return _dec(value, "1") if value.denominator == 1 else _dec(value)


def nights_from_duration(text: str | None) -> int | None:
    """'6 nights / 7 days' -> 6, '1 day' / 'Half day' -> 0."""
    if not text:
        return None
    m = re.search(r"(\d+)\s*night", text, re.IGNORECASE)
    if m:
        return int(m.group(1))
    if re.search(r"\bday\b", text, re.IGNORECASE):
        return 0
    return None


class PricingEngine:
    def __init__(
        self,
        rates: RateBook,
        content: dict[str, TourContentInfo] | None = None,
        margins: MarginOverrides | None = None,
    ):
        self.rates = rates
        self.content = content
        self.margins = margins or MarginOverrides()

    # ------------------------------------------------------------------ public API

    def quote(self, req: QuoteRequest, today: date) -> StaffQuote:
        """Return a priced quote, or a non-priced status with a staff-only reason. Never a guess."""
        tour_id = normalise_id(req.tour_id)
        adults = req.adults + sum(1 for a in req.child_ages if a >= 12)
        children = sum(1 for a in req.child_ages if 2 <= a <= 11)
        infants = sum(1 for a in req.child_ages if a < 2)
        base = {
            "tour_id": tour_id,
            "start_date": req.start_date,
            "adults": adults,
            "children": children,
            "infants": infants,
            "rates_version": self.rates.version,
            "quoted_on": today,
        }
        tour = self.rates.tours.get(tour_id)
        if tour:
            base["tour_name"] = tour.name
            base["end_date"] = req.start_date + timedelta(days=tour.days - 1)
        try:
            return self._price(req, today, tour_id, tour, adults, children, base)
        except _NoPrice as np:
            return StaffQuote(status=np.status, reason=np.reason, **base)

    # ------------------------------------------------------------------ internals

    def _check_quotable(self, tour_id: str, tour: TourRate | None) -> TourRate:
        if tour_id in NOT_QUOTABLE:
            raise _NoPrice(QuoteStatus.NOT_AVAILABLE, NOT_QUOTABLE[tour_id])
        if self.content is not None:
            info = self.content.get(tour_id)
            if info is None or info.status != "published":
                raise _NoPrice(QuoteStatus.NOT_AVAILABLE, f"{tour_id} has no published tour page.")
        if tour is None:
            raise _NoPrice(QuoteStatus.MISSING_RATES, f"No rates for {tour_id} in the rate workbook.")
        if "not launched" in tour.notes.lower():
            raise _NoPrice(QuoteStatus.NOT_AVAILABLE, f"{tour_id} rate note: '{tour.notes}'.")
        if self.content is not None:
            nights = self.content[tour_id].nights
            if nights is not None and nights != tour.nights:
                raise _NoPrice(
                    QuoteStatus.NOT_AVAILABLE,
                    f"{tour_id}: tour page says {nights} night(s), rate sheet has {tour.nights}.",
                )
        if len(tour.hotels) != tour.nights:
            raise _NoPrice(
                QuoteStatus.MISSING_RATES,
                f"{tour_id}: {tour.nights} nights but {len(tour.hotels)} hotel nights in rate sheet.",
            )
        return tour

    def _hotel_row(self, hotel_id: str, night: date) -> HotelRate:
        rows = self.rates.hotels.get(hotel_id, [])
        if not rows:
            raise _NoPrice(QuoteStatus.MISSING_RATES, f"No rates for hotel {hotel_id}.")
        covering = [r for r in rows if r.covers(night)]
        if not covering:
            raise _NoPrice(
                QuoteStatus.EXPIRED_RATES,
                f"Hotel {hotel_id} has no rate covering {night.isoformat()}.",
            )
        first = covering[0]
        if any(not first.same_prices(r) for r in covering[1:]):
            rows_txt = ", ".join(str(r.row) for r in covering)
            raise _NoPrice(
                QuoteStatus.AMBIGUOUS_RATES,
                f"Hotel {hotel_id} has conflicting rates for {night.isoformat()} (rows {rows_txt}).",
            )
        return first

    def _price(self, req, today, tour_id, tour, adults, children, base) -> StaffQuote:
        s = self.rates.settings
        tour = self._check_quotable(tour_id, tour)

        if req.start_date < today:
            raise _NoPrice(QuoteStatus.INVALID_REQUEST, "Start date is in the past.")
        group = adults + children
        if group > s.max_group_size:
            raise _NoPrice(
                QuoteStatus.REFER_TO_SALES,
                f"{group} travellers exceeds the private-tour maximum of {s.max_group_size}.",
            )
        end = req.start_date + timedelta(days=tour.days - 1)
        if s.fx_valid_until and end > s.fx_valid_until:
            raise _NoPrice(
                QuoteStatus.EXPIRED_RATES,
                f"Tour ends {end.isoformat()}, after rates are valid ({s.fx_valid_until.isoformat()}).",
            )
        vehicle = next(
            (v for v in self.rates.vehicles if v.min_travellers <= group <= v.max_travellers),
            None,
        )
        if vehicle is None:
            raise _NoPrice(QuoteStatus.MISSING_RATES, f"No vehicle rate for {group} travellers.")

        lines: list[tuple[str, str, Fraction]] = [
            ("guide", f"Guide {tour.days} day(s)", tour.guide_per_day * tour.days),
            ("vehicle", f"{vehicle.name} {tour.days} day(s)", vehicle.per_day * tour.days),
            (
                "entrance",
                f"Entrance {adults} adult(s), {children} child(ren)",
                tour.entrance_adult * adults + tour.entrance_child * children,
            ),
            (
                "meals",
                f"Meals {tour.days} day(s)",
                tour.meals_per_adult_day * tour.days * (adults + Fraction(children, 2)),
            ),
        ]

        doubles, singles = divmod(adults, 2)
        for i, hotel_id in enumerate(tour.hotels):
            night = req.start_date + timedelta(days=i)
            row = self._hotel_row(hotel_id, night)
            needed = (
                ("double", row.double, doubles),
                ("single", row.single, singles),
                ("extra bed", row.extra_bed, children),
            )
            night_cost = Fraction(0)
            for label, rate, qty in needed:
                if qty == 0:
                    continue
                if rate is None:
                    raise _NoPrice(
                        QuoteStatus.MISSING_RATES,
                        f"Hotel {hotel_id} has no {label} rate for {night.isoformat()} (row {row.row}).",
                    )
                night_cost += rate * qty
            usd = row.currency == "USD"
            lines.append((
                "hotel",
                f"Night {i + 1} {night.isoformat()} {hotel_id} {row.season}: "
                f"{doubles} double, {singles} single, {children} extra bed"
                + (f" (USD contract x {s.fx_lkr_per_usd})" if usd else ""),
                night_cost * (s.fx_lkr_per_usd if usd else 1),
            ))

        cost_lkr = sum((amount for _, _, amount in lines), Fraction(0))
        cost_usd = cost_lkr / s.fx_lkr_per_usd
        if tour.kind == "day":
            margin = self.margins.day if self.margins.day is not None else s.margin_day
        else:
            margin = self.margins.multi if self.margins.multi is not None else s.margin_multi
        sell = cost_usd / (1 - margin)
        price = ceil_to(sell, s.round_to_usd)

        days_to_start = (req.start_date - today).days
        if tour.kind == "day" or days_to_start <= s.full_payment_within_days:
            deposit = price
        else:
            deposit = Fraction(math.ceil(price * s.deposit_multi))
        balance = price - deposit
        balance_due = (
            req.start_date - timedelta(days=s.full_payment_within_days) if balance > 0 else None
        )

        return StaffQuote(
            status=QuoteStatus.PRICED,
            price_usd=_money(price),
            deposit_usd=_money(deposit),
            balance_usd=_money(balance),
            balance_due=balance_due,
            vehicle=vehicle.name,
            cost_lines=[CostLine(category=c, label=l, amount_lkr=_money(a)) for c, l, a in lines],
            cost_lkr=_money(cost_lkr),
            cost_usd=_dec(cost_usd),
            sell_usd_unrounded=_dec(sell),
            margin_pct=_dec(margin * 100, "0.1"),
            gross_profit_pct=_dec((price - cost_usd) / price * 100, "0.1"),
            **base,
        )
