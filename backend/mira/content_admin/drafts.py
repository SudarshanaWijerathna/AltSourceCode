"""AI-drafted tour pages: storage, rendering and the publish step (Req 8).

A draft lives only in the database until a user with the Approver role publishes it. Publishing
writes a normal content page (front matter + Markdown) into MIRA_PUBLISHED_DIR - never into the
dataset folder - and refreshes Mira's catalog and search index, so Mira can answer about it.
Unpublished drafts are never indexed. New tours have no rates, so Mira never prices them.
"""

from __future__ import annotations

import json
import re
import sqlite3
import uuid
from datetime import UTC, date, datetime
from pathlib import Path
from threading import Lock

from pydantic import BaseModel, Field

from mira.enquiries.store import _db_path

_SCHEMA = """
CREATE TABLE IF NOT EXISTS content_drafts (
    id           TEXT PRIMARY KEY,
    tour_id      TEXT NOT NULL,
    command      TEXT NOT NULL,
    title        TEXT NOT NULL,
    draft_json   TEXT NOT NULL,
    markdown     TEXT NOT NULL,
    staff_notes  TEXT NOT NULL DEFAULT '',
    status       TEXT NOT NULL DEFAULT 'draft',   -- draft | published | rejected
    created_by   TEXT NOT NULL,
    created_at   TEXT NOT NULL,
    decided_by   TEXT,
    decided_at   TEXT,
    published_path TEXT,
    trace_id     TEXT
);
"""

CATEGORIES = ("Day tour", "City tour", "Short stay", "Round trip", "Beach stay", "Special interest")
_MONEY = re.compile(r"(?i)(?:from\s+)?(?:usd|us\$|\$|lkr|rs\.?)\s*\d[\d,]*(?:\.\d+)?(?:\s*per\s+\w+)?|\b\d{1,3}\s*%\s*(?:off|discount)")


class DraftDay(BaseModel):
    title: str = Field(description="Short day title, e.g. 'Kandy to Nuwara Eliya by train'.")
    description: str = Field(description="One or two sentences built only from the passages.")


class DraftTour(BaseModel):
    """What the content agent returns; code validates and renders it."""

    title: str
    category: str = Field(description=f"One of: {', '.join(CATEGORIES)}.")
    duration_days: int = Field(ge=1, le=21)
    start: str = Field(description="Where the tour starts, from the passages (e.g. 'Kandy').")
    destinations: list[str] = Field(description="Destination ids from the passages, lower-case (e.g. 'ella').")
    summary: str = Field(description="One or two sentence page intro, built only from the passages.")
    days: list[DraftDay]
    inclusions: list[str] = Field(description="Inclusions consistent with our existing tours in the passages.")
    hotels: list[str] = Field(default_factory=list, description="Only hotels named in the passages.")
    citations: list[int] = Field(description="Numbers of the passages used.")
    notes_for_staff: str = Field(description="Gaps or assumptions the approver must check (e.g. missing photos, unknown hotels).")


def strip_money(text: str) -> str:
    return re.sub(r"\s{2,}", " ", _MONEY.sub("", text)).strip()


def duration_text(days: int) -> str:
    if days == 1:
        return "1 day"
    nights = days - 1
    return f"{nights} night{'s' if nights != 1 else ''} / {days} days"


def validate_draft(d: DraftTour, passages_text: str, known_destinations: set[str]) -> tuple[DraftTour, list[str]]:
    """Deterministic clean-up. Returns (cleaned draft, notes for the approver)."""
    notes: list[str] = []
    if d.category not in CATEGORIES:
        notes.append(f"Category '{d.category}' not recognised; set to Round trip.")
        d.category = "Round trip"
    dests = [re.sub(r"[\s_]+", "-", x.lower().strip()) for x in d.destinations]  # "Nuwara Eliya" -> nuwara-eliya
    unknown = [x for x in dests if x not in known_destinations]
    if unknown:
        notes.append(f"Destinations without a published page were removed: {', '.join(unknown)}.")
    d.destinations = [x for x in dests if x in known_destinations]
    hotels_kept = [h for h in d.hotels if h.lower() in passages_text.lower()]
    if len(hotels_kept) != len(d.hotels):
        notes.append("Hotels not found in our existing pages were removed.")
    d.hotels = hotels_kept
    if len(d.days) != d.duration_days:
        notes.append(f"Itinerary has {len(d.days)} days but duration says {d.duration_days}; duration set to match.")
        d.duration_days = len(d.days)
    before = json.dumps(d.model_dump())
    d.summary = strip_money(d.summary)
    d.inclusions = [strip_money(x) for x in d.inclusions]
    for day in d.days:
        day.description = strip_money(day.description)
    if json.dumps(d.model_dump()) != before:
        notes.append("Prices or discounts in the AI text were removed; prices come only from the rate sheet.")
    notes.append("No rates exist for this new tour: Mira will hand price requests to a specialist "
                 "until Sales adds it to the rate workbook.")
    return d, notes


def render_markdown(tour_id: str, d: DraftTour, status: str, today: date, approved_by: str | None = None) -> str:
    fm = {
        "id": tour_id, "type": "tour", "title": d.title, "status": status,
        "last_updated": today.isoformat(), "category": d.category,
        "duration": duration_text(d.duration_days), "start": d.start,
        "destinations": d.destinations,
    }
    if d.hotels:
        fm["hotels"] = d.hotels
    fm["generated_by"] = "ai-draft"
    if approved_by:
        fm["approved_by"] = approved_by
    lines = ["---", *(f"{k}: {json.dumps(v, ensure_ascii=False)}" for k, v in fm.items()), "---", "",
             f"# {d.title}", "", d.summary, ""]
    for n, day in enumerate(d.days, start=1):
        lines += [f"### Day {n}: {day.title}", "", day.description, ""]
    if d.inclusions:
        lines += ["## Inclusions", *(f"- {x}" for x in d.inclusions), ""]
    return "\n".join(lines)


class DraftStore:
    def __init__(self, db_url: str):
        self._conn = sqlite3.connect(str(_db_path(db_url)), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._lock = Lock()
        with self._lock:
            self._conn.executescript(_SCHEMA)

    def next_tour_id(self, existing_ids: set[str]) -> str:
        with self._lock:
            ids = existing_ids | {r[0] for r in self._conn.execute("SELECT tour_id FROM content_drafts")}
        numbers = [int(m.group(1)) for i in ids if (m := re.fullmatch(r"T(\d+)", i))]
        return f"T{max(numbers, default=0) + 1:02d}"

    def create(self, tour_id: str, command: str, draft: DraftTour, markdown: str, notes: list[str],
               created_by: str, trace_id: str | None) -> dict:
        draft_id = f"DRAFT-{uuid.uuid4().hex[:6].upper()}"
        with self._lock:
            self._conn.execute(
                "INSERT INTO content_drafts (id, tour_id, command, title, draft_json, markdown, staff_notes,"
                " created_by, created_at, trace_id) VALUES (?,?,?,?,?,?,?,?,?,?)",
                (draft_id, tour_id, command, draft.title, draft.model_dump_json(), markdown,
                 "\n".join(notes), created_by, _now(), trace_id),
            )
            self._conn.commit()
        return self.get(draft_id)

    def get(self, draft_id: str) -> dict | None:
        with self._lock:
            row = self._conn.execute("SELECT * FROM content_drafts WHERE id = ?", (draft_id,)).fetchone()
        return dict(row) if row else None

    def list(self) -> list[dict]:
        with self._lock:
            rows = self._conn.execute("SELECT * FROM content_drafts ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]

    def decide(self, draft_id: str, status: str, user: str, published_path: str | None = None,
               markdown: str | None = None) -> dict:
        with self._lock:
            self._conn.execute(
                "UPDATE content_drafts SET status = ?, decided_by = ?, decided_at = ?,"
                " published_path = COALESCE(?, published_path), markdown = COALESCE(?, markdown) WHERE id = ?",
                (status, user, _now(), published_path, markdown, draft_id),
            )
            self._conn.commit()
        return self.get(draft_id)


def publish(store: DraftStore, draft_id: str, approver: str, published_dir: Path, today: date) -> dict:
    """Write the approved page into the published-content folder. Caller refreshes Mira's content."""
    row = store.get(draft_id)
    if row is None:
        raise KeyError(draft_id)
    if row["status"] != "draft":
        raise ValueError(f"{draft_id} is already {row['status']}")
    d = DraftTour.model_validate_json(row["draft_json"])
    markdown = render_markdown(row["tour_id"], d, "published", today, approved_by=approver)
    published_dir.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r"[^a-z0-9]+", "-", d.title.lower()).strip("-")
    path = published_dir / f"{row['tour_id'].lower()}-{slug}.md"
    path.write_text(markdown, encoding="utf-8")
    return store.decide(draft_id, "published", approver, published_path=str(path), markdown=markdown)


def _now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
