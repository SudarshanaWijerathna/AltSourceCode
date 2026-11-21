"""Loads rate_sheet_2026-27.xlsx into typed, cleaned rate tables.

The workbook is read-only input and is never modified. It is a real-world-style
sales handover, so this loader normalises known quirks and records every one it
finds in `RateBook.warnings` instead of failing silently:

- money stored as text ("LKR 28,000")       -> parsed to a number
- dates stored as text ("15/12/2026")       -> parsed as day/month/year
- hotel rows contracted in USD (Notes "USD") -> flagged as USD, converted later
- tour ids written "T-13"                    -> normalised to "T13"
- blank rows, overlapping rate rows, expired rate rows -> reported

Tabs: READ ME, Settings, Seasons, Tours, Hotels, Transport.
"""

from __future__ import annotations

import hashlib
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from fractions import Fraction
from pathlib import Path
from typing import Literal

import openpyxl

Currency = Literal["LKR", "USD"]
TourKind = Literal["day", "multi"]


class RatesLoadError(RuntimeError):
    """The workbook cannot be used for pricing at all (e.g. a Settings value is missing)."""


@dataclass(frozen=True)
class PricingSettings:
    fx_lkr_per_usd: Fraction
    fx_valid_until: date | None
    margin_day: Fraction
    margin_multi: Fraction
    deposit_multi: Fraction
    full_payment_within_days: int
    max_group_size: int
    round_to_usd: int


@dataclass(frozen=True)
class TourRate:
    tour_id: str
    raw_id: str
    name: str
    kind: TourKind
    days: int
    nights: int
    guide_per_day: Fraction
    entrance_adult: Fraction
    entrance_child: Fraction
    meals_per_adult_day: Fraction
    hotels: tuple[str, ...]
    notes: str


@dataclass(frozen=True)
class HotelRate:
    hotel_id: str
    name: str
    season: str
    valid_from: date | None
    valid_to: date | None
    double: Fraction | None
    single: Fraction | None
    extra_bed: Fraction | None
    currency: Currency
    notes: str
    row: int

    def covers(self, night: date) -> bool:
        return (
            self.valid_from is not None
            and self.valid_to is not None
            and self.valid_from <= night <= self.valid_to
        )

    def same_prices(self, other: HotelRate) -> bool:
        return (self.double, self.single, self.extra_bed, self.currency) == (
            other.double, other.single, other.extra_bed, other.currency
        )


@dataclass(frozen=True)
class Vehicle:
    name: str
    min_travellers: int
    max_travellers: int
    per_day: Fraction


@dataclass(frozen=True)
class Season:
    name: str
    start: date
    end: date


@dataclass
class RateBook:
    settings: PricingSettings
    tours: dict[str, TourRate]
    hotels: dict[str, list[HotelRate]]
    vehicles: list[Vehicle]
    seasons: list[Season]
    version: str
    warnings: list[str] = field(default_factory=list)


# --------------------------------------------------------------------------- parsing helpers

_ID_RE = re.compile(r"^\s*([A-Za-z])\s*[-_ ]?\s*(\d+)\s*$")
_EMPTY = {"", "-", "–", "—", "n/a", "na", "none"}


def normalise_id(raw: object) -> str:
    """'T-13' -> 'T13', ' h1 ' -> 'H01'. Unknown shapes are returned stripped and upper-cased."""
    text = str(raw).strip()
    m = _ID_RE.match(text)
    if not m:
        return text.upper()
    return f"{m.group(1).upper()}{int(m.group(2)):02d}"


def _is_empty(value: object) -> bool:
    return value is None or (isinstance(value, str) and value.strip().lower() in _EMPTY)


def parse_money(value: object) -> Fraction | None:
    """Numbers stay numbers; text such as 'LKR 28,000' is parsed. Empty/unparseable -> None."""
    if _is_empty(value):
        return None
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return Fraction(str(value))
    digits = re.sub(r"[^0-9.]", "", str(value))
    if not digits or digits.count(".") > 1:
        return None
    return Fraction(digits)


def parse_date(value: object) -> date | None:
    if _is_empty(value):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    text = str(value).strip()
    for fmt in ("%d/%m/%Y", "%Y-%m-%d", "%d-%m-%Y", "%d %b %Y", "%d %B %Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _cell_ref(sheet: str, row: int, col: str) -> str:
    return f"{sheet}!{col}{row}"


# --------------------------------------------------------------------------- tab loaders

def _load_settings(ws, warnings: list[str]) -> PricingSettings:
    found: dict[str, object] = {}
    fx_until: date | None = None
    for row in ws.iter_rows(min_row=2, values_only=True):
        if not row or _is_empty(row[0]):
            continue
        label = str(row[0]).lower()
        value = row[1] if len(row) > 1 else None
        note = str(row[2]) if len(row) > 2 and row[2] is not None else ""
        if "fx rate" in label:
            found["fx"] = value
            m = re.search(r"until\s+(\d{1,2}\s+\w+\s+\d{4})", note, re.IGNORECASE)
            if m:
                fx_until = parse_date(m.group(1))
        elif "margin" in label and "multi" in label:
            found["margin_multi"] = value
        elif "margin" in label and "day" in label:
            found["margin_day"] = value
        elif "deposit" in label:
            found["deposit"] = value
        elif "full payment" in label:
            found["full_within"] = value
        elif "max group" in label:
            found["max_group"] = value
        elif "round" in label:
            found["round"] = value

    required = ["fx", "margin_day", "margin_multi", "deposit", "full_within", "max_group", "round"]
    missing = [k for k in required if parse_money(found.get(k)) is None]
    if missing:
        raise RatesLoadError(f"Settings tab is missing values for: {', '.join(missing)}")
    if fx_until is None:
        warnings.append("Settings: FX validity date not found in notes; no FX expiry enforced.")

    return PricingSettings(
        fx_lkr_per_usd=parse_money(found["fx"]),
        fx_valid_until=fx_until,
        margin_day=parse_money(found["margin_day"]),
        margin_multi=parse_money(found["margin_multi"]),
        deposit_multi=parse_money(found["deposit"]),
        full_payment_within_days=int(parse_money(found["full_within"])),
        max_group_size=int(parse_money(found["max_group"])),
        round_to_usd=int(parse_money(found["round"])),
    )


def _load_seasons(ws, warnings: list[str]) -> list[Season]:
    seasons: list[Season] = []
    for idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if not row or _is_empty(row[0]):
            continue
        start, end = parse_date(row[1]), parse_date(row[2])
        if start is None or end is None:
            warnings.append(f"Seasons row {idx}: unreadable dates, skipped.")
            continue
        seasons.append(Season(str(row[0]).strip(), start, end))
    return seasons


def _tour_kind(value: object) -> TourKind | None:
    text = str(value or "").lower()
    if "multi" in text:
        return "multi"
    if "day" in text:
        return "day"
    return None


def _load_tours(ws, warnings: list[str]) -> dict[str, TourRate]:
    tours: dict[str, TourRate] = {}
    for idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if not row or _is_empty(row[0]):
            continue
        raw_id = str(row[0]).strip()
        tour_id = normalise_id(raw_id)
        if tour_id != raw_id:
            warnings.append(f"Tours row {idx}: id '{raw_id}' normalised to '{tour_id}'.")
        kind = _tour_kind(row[2])
        if kind is None:
            warnings.append(f"Tours row {idx} ({tour_id}): unknown type '{row[2]}', skipped.")
            continue
        money = [parse_money(v) for v in row[5:9]]
        if any(m is None for m in money) or row[3] is None or row[4] is None:
            warnings.append(f"Tours row {idx} ({tour_id}): missing cost fields, skipped.")
            continue
        hotels_raw = row[9]
        hotels = () if _is_empty(hotels_raw) else tuple(
            normalise_id(h) for h in str(hotels_raw).split(",") if not _is_empty(h)
        )
        nights = int(row[4])
        if len(hotels) != nights:
            warnings.append(
                f"Tours row {idx} ({tour_id}): {nights} nights but {len(hotels)} hotel nights listed."
            )
        notes = str(row[10]).strip() if len(row) > 10 and row[10] is not None else ""
        if notes:
            warnings.append(f"Tours row {idx} ({tour_id}): note '{notes}'.")
        if tour_id in tours:
            warnings.append(f"Tours row {idx}: duplicate tour id {tour_id}, later row ignored.")
            continue
        tours[tour_id] = TourRate(
            tour_id=tour_id,
            raw_id=raw_id,
            name=str(row[1]).strip(),
            kind=kind,
            days=int(row[3]),
            nights=nights,
            guide_per_day=money[0],
            entrance_adult=money[1],
            entrance_child=money[2],
            meals_per_adult_day=money[3],
            hotels=hotels,
            notes=notes,
        )
    return tours


def _load_hotels(ws, warnings: list[str]) -> dict[str, list[HotelRate]]:
    rows = list(ws.iter_rows(values_only=True))
    header_idx = next(
        (i for i, r in enumerate(rows) if r and str(r[0] or "").strip().lower() == "hotel id"), None
    )
    if header_idx is None:
        raise RatesLoadError("Hotels tab: header row with 'Hotel ID' not found.")

    hotels: dict[str, list[HotelRate]] = {}
    for offset, row in enumerate(rows[header_idx + 1:], start=header_idx + 2):
        if not row or all(_is_empty(v) for v in row):
            warnings.append(f"Hotels row {offset}: blank row skipped.")
            continue
        hotel_id = normalise_id(row[0])
        notes = str(row[8]).strip() if len(row) > 8 and row[8] is not None else ""
        currency: Currency = "USD" if "usd" in notes.lower() else "LKR"

        for col, value in zip("DE", row[3:5]):
            if isinstance(value, str) and parse_date(value) is not None:
                warnings.append(f"{_cell_ref('Hotels', offset, col)}: date stored as text '{value}'.")
        for col, value in zip("FGH", row[5:8]):
            if isinstance(value, str) and parse_money(value) is not None:
                warnings.append(f"{_cell_ref('Hotels', offset, col)}: amount stored as text '{value}'.")

        rate = HotelRate(
            hotel_id=hotel_id,
            name=str(row[1] or "").strip(),
            season=str(row[2] or "").strip(),
            valid_from=parse_date(row[3]),
            valid_to=parse_date(row[4]),
            double=parse_money(row[5]),
            single=parse_money(row[6]),
            extra_bed=parse_money(row[7]),
            currency=currency,
            notes=notes,
            row=offset,
        )
        if rate.valid_from is None or rate.valid_to is None:
            warnings.append(f"Hotels row {offset} ({hotel_id}): unreadable validity dates.")
        if currency == "USD":
            warnings.append(f"Hotels row {offset} ({hotel_id}): contracted in USD, not LKR.")
        elif rate.double is not None and rate.double < 1000:
            warnings.append(
                f"Hotels row {offset} ({hotel_id}): double rate {rate.double} looks too low for LKR."
            )
        for label, value in (("double", rate.double), ("single", rate.single), ("extra bed", rate.extra_bed)):
            if value is None:
                warnings.append(f"Hotels row {offset} ({hotel_id}): no {label} rate.")
        if notes and currency == "LKR":
            warnings.append(f"Hotels row {offset} ({hotel_id}): note '{notes}'.")
        hotels.setdefault(hotel_id, []).append(rate)

    for hotel_id, rates in hotels.items():
        for i, a in enumerate(rates):
            for b in rates[i + 1:]:
                if a.valid_from and a.valid_to and b.valid_from and b.valid_to and (
                    a.valid_from <= b.valid_to and b.valid_from <= a.valid_to
                ) and not a.same_prices(b):
                    warnings.append(
                        f"Hotels {hotel_id}: rows {a.row} and {b.row} overlap "
                        f"({max(a.valid_from, b.valid_from)} to {min(a.valid_to, b.valid_to)}) "
                        "with different rates."
                    )
    return hotels


def _load_transport(ws, warnings: list[str]) -> list[Vehicle]:
    vehicles: list[Vehicle] = []
    for idx, row in enumerate(ws.iter_rows(min_row=2, values_only=True), start=2):
        if not row or _is_empty(row[0]):
            continue
        per_day = parse_money(row[3])
        if per_day is None or row[1] is None or row[2] is None:
            warnings.append(f"Transport row {idx}: incomplete, skipped.")
            continue
        vehicles.append(Vehicle(str(row[0]).strip(), int(row[1]), int(row[2]), per_day))
    return sorted(vehicles, key=lambda v: v.min_travellers)


# --------------------------------------------------------------------------- entrypoint

def load_ratebook(path: Path) -> RateBook:
    data = Path(path).read_bytes()
    version = f"{Path(path).name}@{hashlib.sha256(data).hexdigest()[:12]}"
    wb = openpyxl.load_workbook(path, data_only=True, read_only=True)
    try:
        warnings: list[str] = []
        settings = _load_settings(wb["Settings"], warnings)
        book = RateBook(
            settings=settings,
            seasons=_load_seasons(wb["Seasons"], warnings),
            tours=_load_tours(wb["Tours"], warnings),
            hotels=_load_hotels(wb["Hotels"], warnings),
            vehicles=_load_transport(wb["Transport"], warnings),
            version=version,
            warnings=warnings,
        )
    finally:
        wb.close()

    if settings.fx_valid_until:
        for hotel_id, rates in book.hotels.items():
            last = max((r.valid_to for r in rates if r.valid_to), default=None)
            if last and last < settings.fx_valid_until:
                warnings.append(f"Hotels {hotel_id}: rates end on {last}, before {settings.fx_valid_until}.")
    for tour in book.tours.values():
        for hotel_id in tour.hotels:
            if hotel_id not in book.hotels:
                warnings.append(f"Tour {tour.tour_id}: hotel {hotel_id} has no rates.")
    return book
