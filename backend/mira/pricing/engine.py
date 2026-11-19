"""Pricing function. Implements the rules on the workbook's READ ME tab.

Inputs come from mira.data.rates (loaded from the workbook as-is).
"""

from datetime import date

from mira.pricing.models import QuoteRequest, StaffQuote


def quote(req: QuoteRequest, today: date) -> StaffQuote:
    """Return a priced quote, or a MISSING/EXPIRED status - never a guess."""
    raise NotImplementedError("Implement from rate_sheet_2026-27.xlsx READ ME rules")
