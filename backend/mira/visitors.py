"""Returning visitors (Req 2).

The browser keeps a random visitor id (no personal data) and sends it inside the AG-UI thread id
("v-<visitor>.<session>"). We remember the trip profile Mira learned and the visitor's last
priced quote. When the visitor comes back in a new session:

- the welcome endpoint re-prices the last quote with the pricing engine *today* and shows it only
  if the price is unchanged (never a stale price);
- the first turn of the new session starts from the remembered profile, so Mira does not ask
  again for the tour, dates or travellers it already knows.
"""

from __future__ import annotations

import json
import re
import sqlite3
from datetime import UTC, date, datetime
from threading import Lock

from mira.enquiries.store import _db_path
from mira.pricing.engine import PricingEngine
from mira.pricing.models import QuoteRequest, QuoteStatus

VISITOR_ID = re.compile(r"^v-[a-z0-9]{8,40}$")
_THREAD = re.compile(r"^(v-[a-z0-9]{8,40})\.[A-Za-z0-9_-]{1,64}$")

_SCHEMA = """
CREATE TABLE IF NOT EXISTS visitors (
    visitor_id      TEXT PRIMARY KEY,
    profile_json    TEXT NOT NULL DEFAULT '{}',
    last_enquiry_id TEXT,
    visits          INTEGER NOT NULL DEFAULT 0,
    last_session    TEXT,
    updated_at      TEXT NOT NULL
);
"""

# Only trip facts are remembered; never names, emails or phone numbers.
REMEMBERED = ("tour_id", "start_date", "adults", "children_count", "child_ages", "traveller_type",
              "trip_type", "destinations", "duration_days")


def visitor_from_thread(thread_id: str) -> str | None:
    m = _THREAD.match(thread_id or "")
    return m.group(1) if m else None


class VisitorStore:
    def __init__(self, db_url: str):
        self._conn = sqlite3.connect(str(_db_path(db_url)), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = Lock()
        with self._lock:
            self._conn.executescript(_SCHEMA)

    def get(self, visitor_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM visitors WHERE visitor_id = ?", (visitor_id,)).fetchone()
        if not row:
            return None
        data = dict(row)
        data["profile"] = json.loads(data.pop("profile_json"))
        return data

    def remember(self, visitor_id: str, session_id: str, profile: dict, enquiry_id: str | None) -> None:
        trip = {k: profile[k] for k in REMEMBERED if profile.get(k) not in (None, [], "")}
        now = datetime.now(UTC).isoformat(timespec="seconds")
        with self._lock:
            old = self._conn.execute("SELECT last_session FROM visitors WHERE visitor_id = ?",
                                     (visitor_id,)).fetchone()
            new_visit = old is None or old["last_session"] != session_id
            self._conn.execute(
                "INSERT INTO visitors (visitor_id, profile_json, last_enquiry_id, visits, last_session, updated_at)"
                " VALUES (?, ?, ?, 1, ?, ?)"
                " ON CONFLICT(visitor_id) DO UPDATE SET profile_json = excluded.profile_json,"
                " last_enquiry_id = COALESCE(excluded.last_enquiry_id, visitors.last_enquiry_id),"
                " visits = visitors.visits + ?, last_session = excluded.last_session,"
                " updated_at = excluded.updated_at",
                (visitor_id, json.dumps(trip), enquiry_id, session_id, now, 1 if new_visit and old else 0),
            )
            self._conn.commit()


def welcome(visitor_id: str, visitors: VisitorStore, enquiries, engine: PricingEngine,
            tours: dict, today: date) -> dict:
    """What a returning visitor sees before typing: their last quote, re-checked today."""
    v = visitors.get(visitor_id) if VISITOR_ID.match(visitor_id or "") else None
    if not v:
        return {"returning": False}
    out: dict = {"returning": True, "profile": v["profile"], "last_quote": None}
    enquiry = enquiries.get(v["last_enquiry_id"]) if v.get("last_enquiry_id") else None
    if not enquiry or enquiry["status"] != "priced":
        return out
    q = enquiry["quote"]
    tour = tours.get(q["tour_id"])
    # quote["adults"] already counts children aged 12+, so only under-12s are passed as children.
    ages = [a for a in v["profile"].get("child_ages", []) if a < 12] \
        if v["profile"].get("tour_id") == q["tour_id"] else []
    try:
        fresh = engine.quote(QuoteRequest(tour_id=q["tour_id"], start_date=date.fromisoformat(q["start_date"]),
                                          adults=q["adults"], child_ages=ages), today)
    except ValueError:
        fresh = None
    unchanged = bool(
        fresh and fresh.status is QuoteStatus.PRICED
        and str(fresh.price_usd) == str(q["price_usd"]) and str(fresh.deposit_usd) == str(q["deposit_usd"])
    )
    out["last_quote"] = {
        "enquiry_id": enquiry["id"],
        "tour_id": q["tour_id"],
        "tour_title": tour.title if tour else q.get("tour_name"),
        "start_date": q["start_date"],
        "adults": q["adults"], "children": q.get("children", 0), "infants": q.get("infants", 0),
        "still_valid": unchanged,
        # Prices are shown only when re-pricing today gives exactly the same result.
        "price_usd": q["price_usd"] if unchanged else None,
        "deposit_usd": q["deposit_usd"] if unchanged else None,
        "balance_usd": q.get("balance_usd") if unchanged else None,
        "balance_due": q.get("balance_due") if unchanged else None,
        "booked": bool(enquiry.get("booking_ref")),
    }
    return out
