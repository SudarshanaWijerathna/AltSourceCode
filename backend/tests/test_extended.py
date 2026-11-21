"""Extended requirements: R7 staff enquiries, R8 approve AI-written content, R2 returning visitors."""

from __future__ import annotations

import uuid
from datetime import date

import pytest
from fastapi.testclient import TestClient

from mira import main, staff_api
from mira.config import REPO_ROOT, get_settings
from mira.content_admin.drafts import DraftDay, DraftStore, DraftTour
from mira.data.tours import published_tours
from mira.retrieval import get_index
from mira.state import TurnAnalysis
from mira.visitors import welcome
from tests.test_graph import FakeAnalyzer, make_mira

STAFF = {"x-staff-key": "demo-staff-key"}
APPROVER = {"x-staff-key": "demo-approver-key"}


@pytest.fixture
def app(monkeypatch, tmp_path):
    """API wired to a Mira with fake LLMs, an in-memory DB and a temporary published-content dir."""
    analyzer = FakeAnalyzer()
    mira, _, _ = make_mira(analyzer)
    monkeypatch.setattr(main, "get_mira", lambda: mira)
    monkeypatch.setattr(get_settings(), "mira_published_dir", tmp_path)
    monkeypatch.setattr(staff_api, "_drafts", DraftStore("sqlite:///:memory:"))
    yield TestClient(main.app), mira, analyzer
    published_tours.cache_clear()
    get_index.cache_clear()


def A(**kw):
    return TurnAnalysis(**kw)


# --------------------------------------------------------------------------- R7 staff enquiries

def test_staff_endpoints_require_a_valid_key(app):
    http, _, _ = app
    assert http.get("/staff/enquiries").status_code == 401
    assert http.get("/staff/enquiries", headers={"x-staff-key": "wrong"}).status_code == 401
    assert http.get("/staff/me", headers=STAFF).json() == {"name": "sam", "role": "staff", "can_publish": False}


def test_enquiry_list_shows_staff_fields_and_accepts_notes(app):
    http, mira, analyzer = app
    analyzer.queue.append(A(intent="price_request", tour_id="T09", start_date="2027-05-03", adults=2))
    mira.turn("s1", "Cultural Triangle for 2 from 3 May 2027")
    rows = http.get("/staff/enquiries", headers=STAFF).json()
    row = rows[0]
    assert (row["price_usd"], row["deposit_usd"], row["cost_usd"], row["gross_profit_pct"]) == ("2125", "532", "1591.67", "25.1")
    assert row["cost_lines"] and row["follow_up_status"] == "new"
    res = http.patch(f"/staff/enquiries/{row['id']}", headers=STAFF,
                     json={"notes": "Called, wants a sea-view room", "follow_up_status": "contacted"})
    assert res.status_code == 200 and res.json()["follow_up_status"] == "contacted"
    assert http.patch(f"/staff/enquiries/{row['id']}", headers=STAFF,
                      json={"follow_up_status": "teleported"}).status_code == 422


# --------------------------------------------------------------------------- R8 content approval

class FakeDrafter:
    def __init__(self, title):
        self.title = title
        self.prompts = []

    def __call__(self, messages, callbacks):
        self.prompts.append(messages[0].content)
        return DraftTour(
            title=self.title, category="Round trip", duration_days=2, start="Kandy",
            destinations=["ella", "nuwara-eliya", "atlantis"],
            summary="Tea country by train, from USD 999 per person.",
            days=[DraftDay(title="Kandy to Nuwara Eliya", description="Take the hill-country train."),
                  DraftDay(title="Ella", description="Walk to Little Adam's Peak and see the Nine Arches Bridge.")],
            inclusions=["English-speaking guide"], hotels=["Hotel Suisse", "Imaginary Palace"],
            citations=[1, 2], notes_for_staff="No licensed Ella photos were found; add images before launch.",
        )


def test_draft_needs_approver_and_is_invisible_until_published(app, monkeypatch, tmp_path):
    http, mira, _ = app
    title = f"Hill Country Rails {uuid.uuid4().hex[:4]}"
    monkeypatch.setattr(staff_api, "_drafter", FakeDrafter(title))
    dataset_before = sorted(p.name for p in (REPO_ROOT / "docs").rglob("*"))

    res = http.post("/staff/drafts", headers=STAFF, json={"command": "Add a 5-day Hill Country tour using the Ella photos"})
    assert res.status_code == 200
    draft = res.json()
    assert draft["status"] == "draft" and draft["tour_id"].startswith("T")
    md, notes = draft["markdown"], draft["staff_notes"]
    assert "USD 999" not in md and "Imaginary Palace" not in md and "atlantis" not in md
    assert "photos" in notes and "No rates exist" in notes and "Prices or discounts" in notes

    # Unpublished: not in the catalog, not retrievable, not quotable.
    assert draft["tour_id"] not in mira.deps.tours
    assert all(title not in h.chunk.title for h in mira.deps.index.search(title))

    assert http.post(f"/staff/drafts/{draft['id']}/publish", headers=STAFF).status_code == 403
    res = http.post(f"/staff/drafts/{draft['id']}/publish", headers=APPROVER)
    assert res.status_code == 200 and res.json()["status"] == "published" and res.json()["decided_by"] == "ana"
    assert http.post(f"/staff/drafts/{draft['id']}/publish", headers=APPROVER).status_code == 409

    # Published: a normal page in the published dir; Mira can now find it; the dataset is untouched.
    assert list(tmp_path.glob("*.md"))
    assert draft["tour_id"] in mira.deps.tours
    assert any(title == h.chunk.title for h in mira.deps.index.search(title))
    assert sorted(p.name for p in (REPO_ROOT / "docs").rglob("*")) == dataset_before


def test_new_tour_is_never_priced(app, monkeypatch):
    http, mira, analyzer = app
    title = f"Tea Trails {uuid.uuid4().hex[:4]}"
    monkeypatch.setattr(staff_api, "_drafter", FakeDrafter(title))
    draft = http.post("/staff/drafts", headers=STAFF, json={"command": "Add a 2-day tea tour"}).json()
    http.post(f"/staff/drafts/{draft['id']}/publish", headers=APPROVER)
    analyzer.queue.append(A(intent="price_request", tour_id=draft["tour_id"], start_date="2027-05-03", adults=2))
    r = mira.turn("s-new", f"How much is {title} for 2 from 3 May 2027?")
    assert r.quote is None and r.needs_specialist


def test_staff_cannot_reject_and_approver_can(app, monkeypatch):
    http, _, _ = app
    monkeypatch.setattr(staff_api, "_drafter", FakeDrafter("Rejected Tour"))
    draft = http.post("/staff/drafts", headers=STAFF, json={"command": "Add a tour"}).json()
    assert http.post(f"/staff/drafts/{draft['id']}/reject", headers=STAFF).status_code == 403
    assert http.post(f"/staff/drafts/{draft['id']}/reject", headers=APPROVER).json()["status"] == "rejected"


# --------------------------------------------------------------------------- R2 returning visitors

def test_returning_visitor_is_greeted_with_last_quote_and_not_asked_again(app):
    http, mira, analyzer = app
    visitor = "v-" + uuid.uuid4().hex[:12]
    analyzer.queue += [
        A(intent="price_request", tour_id="T09", start_date="2027-05-03", adults=2),
        A(intent="price_request", children_count=1, child_ages=[8]),   # new session: only the change
    ]
    first = mira.turn(f"{visitor}.s1", "Cultural Triangle for 2 from 3 May 2027", visitor_id=visitor)
    assert first.quote["price_usd"] == "2125"

    hello = http.get(f"/visitor/{visitor}/welcome").json()
    assert hello["returning"] and hello["last_quote"]["still_valid"]
    assert (hello["last_quote"]["price_usd"], hello["last_quote"]["tour_id"]) == ("2125", "T09")

    second = mira.turn(f"{visitor}.s2", "Can you add our son, he's 8?", visitor_id=visitor)
    assert second.quote is not None, "tour, dates and adults were remembered, so no question is needed"
    assert second.quote["tour_id"] == "T09" and second.quote["children"] == 1


def test_welcome_hides_price_if_it_no_longer_matches(app):
    http, mira, analyzer = app
    visitor = "v-" + uuid.uuid4().hex[:12]
    analyzer.queue.append(A(intent="price_request", tour_id="T01", start_date="2027-01-10", adults=2))
    r = mira.turn(f"{visitor}.s1", "Sigiriya for 2 on 10 Jan 2027", visitor_id=visitor)
    # Pretend the stored quote came from older rates: it no longer matches today's price.
    stale = '{"tour_id":"T01","start_date":"2027-01-10","adults":2,"price_usd":"300","deposit_usd":"300"}'
    mira.deps.store._update(r.enquiry_id, quote_json=stale)
    last = http.get(f"/visitor/{visitor}/welcome").json()["last_quote"]
    assert last["still_valid"] is False and last["price_usd"] is None


def test_unknown_or_malformed_visitor_is_not_returning(app):
    http, _, _ = app
    assert http.get("/visitor/v-doesnotexist00/welcome").json() == {"returning": False}
    assert http.get("/visitor/not-a-visitor-id/welcome").json() == {"returning": False}


def test_welcome_when_past_dates_hide_the_price(app):
    _, mira, analyzer = app
    visitor = "v-" + uuid.uuid4().hex[:12]
    analyzer.queue.append(A(intent="price_request", tour_id="T01", start_date="2027-01-10", adults=2))
    mira.turn(f"{visitor}.s1", "Sigiriya for 2 on 10 Jan 2027", visitor_id=visitor)
    later = date(2027, 2, 1)  # the trip date has now passed
    out = welcome(visitor, mira.visitors, mira.deps.store, mira.deps.engine, mira.deps.tours, later)
    assert out["last_quote"]["still_valid"] is False and out["last_quote"]["price_usd"] is None
