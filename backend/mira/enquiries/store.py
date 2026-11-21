"""Private enquiry store (SQLite). Every quote attempt is saved with its staff breakdown
and the Langfuse trace id that produced it. Traveller contact details are added later
by the booking form and are never sent to tracing.
"""

from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock

from mira.config import REPO_ROOT
from mira.pricing.models import StaffQuote

_SCHEMA = """
CREATE TABLE IF NOT EXISTS enquiries (
    id               TEXT PRIMARY KEY,
    created_at       TEXT NOT NULL,
    session_id       TEXT NOT NULL,
    tour_id          TEXT,
    status           TEXT NOT NULL,
    needs_specialist INTEGER NOT NULL,
    reason           TEXT,
    price_usd        TEXT,
    deposit_usd      TEXT,
    cost_usd         TEXT,
    gross_profit_pct TEXT,
    quote_json       TEXT NOT NULL,
    trace_id         TEXT,
    follow_up_status TEXT NOT NULL DEFAULT 'new',
    notes            TEXT NOT NULL DEFAULT ''
);
CREATE INDEX IF NOT EXISTS enquiries_session ON enquiries(session_id);
"""
_ADDED_COLUMNS = ("contact_name", "contact_email", "contact_phone", "booking_ref")


def _db_path(db_url: str) -> Path:
    """sqlite:///./data/mira.db -> <repo>/data/mira.db (relative paths resolve from the repo root)."""
    if not db_url.startswith("sqlite:///"):
        raise ValueError(f"Only sqlite:/// URLs are supported, got {db_url!r}")
    raw = db_url.removeprefix("sqlite:///")
    if raw == ":memory:":
        return Path(raw)
    path = Path(raw)
    return path if path.is_absolute() else (REPO_ROOT / path).resolve()


class EnquiryStore:
    def __init__(self, db_url: str):
        self.path = _db_path(db_url)
        if str(self.path) != ":memory:":
            self.path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(str(self.path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = Lock()
        with self._lock:
            self._conn.executescript(_SCHEMA)
            have = {r[1] for r in self._conn.execute("PRAGMA table_info(enquiries)")}
            for column in _ADDED_COLUMNS:
                if column not in have:  # databases created before these columns existed
                    self._conn.execute(f"ALTER TABLE enquiries ADD COLUMN {column} TEXT")
            self._conn.commit()

    def _update(self, enquiry_id: str, **fields) -> None:
        sets = ", ".join(f"{k} = ?" for k in fields)
        with self._lock:
            self._conn.execute(f"UPDATE enquiries SET {sets} WHERE id = ?", (*fields.values(), enquiry_id))
            self._conn.commit()

    def save_contact(self, enquiry_id: str, name: str, email: str, phone: str | None) -> None:
        """Personal details live only here (never in traces or eval reports)."""
        self._update(enquiry_id, contact_name=name, contact_email=email, contact_phone=phone)

    def confirm_booking(self, enquiry_id: str, booking_ref: str) -> None:
        self._update(enquiry_id, booking_ref=booking_ref, follow_up_status="booked")

    def set_follow_up(self, enquiry_id: str, status: str) -> None:
        self._update(enquiry_id, follow_up_status=status)

    def update_staff_fields(self, enquiry_id: str, notes: str | None, follow_up_status: str | None) -> dict | None:
        fields = {k: v for k, v in (("notes", notes), ("follow_up_status", follow_up_status)) if v is not None}
        if fields:
            self._update(enquiry_id, **fields)
        return self.get(enquiry_id)

    def save_quote(self, quote: StaffQuote, session_id: str, trace_id: str | None) -> str:
        enquiry_id = f"ENQ-{uuid.uuid4().hex[:8].upper()}"
        row = (
            enquiry_id,
            datetime.now(UTC).isoformat(timespec="seconds"),
            session_id,
            quote.tour_id,
            quote.status.value,
            int(quote.status.needs_specialist),
            quote.reason,
            _s(quote.price_usd),
            _s(quote.deposit_usd),
            _s(quote.cost_usd),
            _s(quote.gross_profit_pct),
            quote.model_dump_json(),
            trace_id,
        )
        with self._lock:
            self._conn.execute(
                "INSERT INTO enquiries (id, created_at, session_id, tour_id, status, needs_specialist,"
                " reason, price_usd, deposit_usd, cost_usd, gross_profit_pct, quote_json, trace_id)"
                " VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                row,
            )
            self._conn.commit()
        return enquiry_id

    def save_request(self, session_id: str, kind: str, details: dict, trace_id: str | None) -> str:
        """Save a request that has no quote (custom trip, unknown tour) for the sales team."""
        enquiry_id = f"ENQ-{uuid.uuid4().hex[:8].upper()}"
        with self._lock:
            self._conn.execute(
                "INSERT INTO enquiries (id, created_at, session_id, tour_id, status, needs_specialist,"
                " reason, quote_json, trace_id) VALUES (?,?,?,?,?,?,?,?,?)",
                (
                    enquiry_id,
                    datetime.now(UTC).isoformat(timespec="seconds"),
                    session_id,
                    details.get("tour_id"),
                    kind,
                    1,
                    kind.replace("_", " "),
                    json.dumps(details, default=str),
                    trace_id,
                ),
            )
            self._conn.commit()
        return enquiry_id

    def get(self, enquiry_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM enquiries WHERE id = ?", (enquiry_id,)).fetchone()
        return _row(row) if row else None

    def list(self, limit: int = 200) -> list[dict]:
        with self._lock:
            rows = self._conn.execute(
                "SELECT * FROM enquiries ORDER BY created_at DESC LIMIT ?", (limit,)
            ).fetchall()
        return [_row(r) for r in rows]


def _s(value) -> str | None:
    return None if value is None else str(value)


def _row(row: sqlite3.Row) -> dict:
    data = dict(row)
    data["needs_specialist"] = bool(data["needs_specialist"])
    data["quote"] = json.loads(data.pop("quote_json"))
    return data
