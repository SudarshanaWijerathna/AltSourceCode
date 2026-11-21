"""Mock booking and payment.

The booking form sends the quote id (the private enquiry id) and contact details. The amount
charged is always the stored quote's deposit - the browser never sends a price. Payment and
the booking system are mocked; `simulate` lets the demo show both failure paths. Every outcome
is a friendly message with a way forward (HTTP 200), never an error page.

Contact details are stored with the private enquiry only; they are not sent to tracing.
"""

from __future__ import annotations

import logging
import uuid
from typing import Literal

from pydantic import BaseModel, EmailStr, Field

from mira.enquiries.store import EnquiryStore

log = logging.getLogger(__name__)

Simulate = Literal["success", "payment_declined", "booking_unavailable"]


class BookingRequest(BaseModel):
    quote_id: str = Field(min_length=4, max_length=40)
    name: str = Field(min_length=1, max_length=120)
    email: EmailStr
    phone: str | None = Field(None, max_length=40)
    simulate: Simulate = "success"


class BookingResult(BaseModel):
    status: Literal["confirmed", "payment_failed", "booking_failed", "not_bookable"]
    message: str
    next_step: str
    booking_ref: str | None = None
    deposit_usd: str | None = None


def book(req: BookingRequest, store: EnquiryStore) -> BookingResult:
    enquiry = store.get(req.quote_id)
    if not enquiry or enquiry["status"] != "priced" or not enquiry.get("deposit_usd"):
        return BookingResult(
            status="not_bookable",
            message="I couldn't find a confirmed price for this trip, so I can't take a booking for it yet.",
            next_step="Ask me for a fresh quote, or leave your details and our team will contact you.",
        )
    if enquiry.get("booking_ref"):
        return BookingResult(
            status="confirmed", booking_ref=enquiry["booking_ref"], deposit_usd=enquiry["deposit_usd"],
            message=f"This trip is already booked. Your reference is {enquiry['booking_ref']}.",
            next_step="We have emailed your confirmation. Reply to it if anything changes.",
        )

    store.save_contact(req.quote_id, req.name, str(req.email), req.phone)
    deposit = enquiry["deposit_usd"]

    if req.simulate == "payment_declined":
        store.set_follow_up(req.quote_id, "payment_failed")
        return BookingResult(
            status="payment_failed", deposit_usd=deposit,
            message="Your card wasn't charged: the payment was declined by the bank.",
            next_step="You can try another card, or we can hold this price and send you a secure "
                      "payment link by email. Our team has your details and will follow up.",
        )
    if req.simulate == "booking_unavailable":
        store.set_follow_up(req.quote_id, "booking_failed")
        return BookingResult(
            status="booking_failed", deposit_usd=deposit,
            message="Our booking system is not responding right now, so nothing has been charged.",
            next_step="Your quote is saved. A travel specialist will confirm the booking with you "
                      "by email, usually within one working day.",
        )

    ref = f"CC-{uuid.uuid4().hex[:6].upper()}"
    store.confirm_booking(req.quote_id, ref)
    return BookingResult(
        status="confirmed", booking_ref=ref, deposit_usd=deposit,
        message=f"Booked. Your reference is {ref}. We've taken your deposit of USD {deposit} (test mode).",
        next_step="You'll receive a confirmation email with your itinerary and payment schedule.",
    )
