"""AG-UI endpoint and mock booking tests (no LLM, no network)."""

import json
from datetime import date

import pytest
from ag_ui.core import RunAgentInput
from fastapi.testclient import TestClient

from mira import main
from mira.agent import TurnResult
from mira.agui import turn_events
from mira.booking import BookingRequest, book
from mira.enquiries.store import EnquiryStore
from mira.pricing import get_engine
from mira.pricing.models import QuoteRequest

TODAY = date(2026, 11, 19)
TOUR_CARD = {"component": "tour_card", "tour_id": "T01", "title": "Sigiriya", "duration": "1 day",
             "summary": "A long day.", "source_path": "docs/x.md"}


def run_input(text="Sigiriya for 2 on 10 Jan 2027"):
    return RunAgentInput.model_validate({
        "threadId": "t1", "runId": "r1", "state": {}, "tools": [], "context": [], "forwardedProps": {},
        "messages": [{"id": "m1", "role": "user", "content": text}],
    })


def test_events_stream_text_then_validated_components():
    ui = [TOUR_CARD, {"component": "free_html", "html": "<script>x</script>"}]
    events = turn_events(run_input(), "Hello " * 30, ui)
    types = [e.type.value for e in events]
    assert types[0] == "RUN_STARTED" and types[-1] == "RUN_FINISHED"
    assert types.count("TEXT_MESSAGE_CONTENT") >= 2  # streamed in chunks
    starts = [e for e in events if e.type.value == "TOOL_CALL_START"]
    assert [s.tool_call_name for s in starts] == ["show_tour_card"], "invalid component must be dropped"
    args = next(e for e in events if e.type.value == "TOOL_CALL_ARGS")
    assert json.loads(args.delta)["tour_id"] == "T01"
    text_id = next(e for e in events if e.type.value == "TEXT_MESSAGE_START").message_id
    assert starts[0].parent_message_id == text_id


class FakeMira:
    def __init__(self):
        self.calls = []

    def turn(self, session_id, message, tags=None, visitor_id=None):
        self.calls.append((session_id, message))
        return TurnResult(reply="Here you go.", ui=[TOUR_CARD])


@pytest.fixture
def client(monkeypatch):
    fake = FakeMira()
    monkeypatch.setattr(main, "get_mira", lambda: fake)
    return TestClient(main.app), fake


def test_agent_endpoint_streams_sse_for_latest_user_message(client):
    http, fake = client
    body = run_input().model_dump(by_alias=True)
    body["messages"].insert(0, {"id": "m0", "role": "user", "content": "earlier message"})
    res = http.post("/agent", json=body, headers={"accept": "text/event-stream"})
    assert res.status_code == 200
    events = [json.loads(line[6:]) for line in res.text.splitlines() if line.startswith("data: ")]
    assert fake.calls == [("t1", "Sigiriya for 2 on 10 Jan 2027")]
    assert [e["type"] for e in events][:2] == ["RUN_STARTED", "TEXT_MESSAGE_START"]
    assert any(e["type"] == "TOOL_CALL_START" and e["toolCallName"] == "show_tour_card" for e in events)


# --------------------------------------------------------------------------- mock booking

@pytest.fixture
def store():
    s = EnquiryStore("sqlite:///:memory:")
    q = get_engine().quote(QuoteRequest(tour_id="T09", start_date=date(2027, 5, 3), adults=2), TODAY)
    s.enquiry_id = s.save_quote(q, "sess", None)
    return s


def req(store, simulate="success"):
    return BookingRequest(quote_id=store.enquiry_id, name="Test Traveller", email="test@example.com",
                          simulate=simulate)


def test_booking_charges_stored_deposit_and_saves_contact(store):
    r = book(req(store), store)
    assert r.status == "confirmed" and r.deposit_usd == "532" and r.booking_ref.startswith("CC-")
    row = store.get(store.enquiry_id)
    assert row["contact_email"] == "test@example.com" and row["follow_up_status"] == "booked"
    again = book(req(store), store)
    assert again.status == "confirmed" and again.booking_ref == r.booking_ref


@pytest.mark.parametrize("simulate, status, follow_up", [
    ("payment_declined", "payment_failed", "payment_failed"),
    ("booking_unavailable", "booking_failed", "booking_failed"),
])
def test_failures_are_friendly_with_a_way_forward(store, simulate, status, follow_up):
    r = book(req(store, simulate), store)
    assert r.status == status and r.next_step and "error" not in r.message.lower()
    assert store.get(store.enquiry_id)["follow_up_status"] == follow_up


def test_unpriced_enquiry_is_not_bookable(store):
    flagged = get_engine().quote(QuoteRequest(tour_id="T11", start_date=date(2027, 1, 20), adults=2), TODAY)
    eid = store.save_quote(flagged, "sess", None)
    r = book(BookingRequest(quote_id=eid, name="A", email="a@example.com"), store)
    assert r.status == "not_bookable" and r.next_step


def test_booking_endpoint_never_errors_for_unknown_quote(monkeypatch):
    store = EnquiryStore("sqlite:///:memory:")
    fake = type("M", (), {"deps": type("D", (), {"store": store})})()
    monkeypatch.setattr(main, "get_mira", lambda: fake)
    http = TestClient(main.app)
    res = http.post("/booking", json={"quote_id": "ENQ-NOPE", "name": "A", "email": "a@example.com"})
    assert res.status_code == 200 and res.json()["status"] == "not_bookable"
