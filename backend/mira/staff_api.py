"""Staff and visitor HTTP API.

Staff (X-Staff-Key header, roles checked in code - mira/auth):
  GET   /staff/me
  GET   /staff/enquiries                 private enquiries: price, deposit, cost, GP%, flag, trace (Req 7)
  PATCH /staff/enquiries/{id}            notes and follow-up status (Req 7)
  GET   /staff/drafts                    AI-written drafts (Req 8)
  POST  /staff/drafts                    staff command -> content agent -> draft (Req 8)
  POST  /staff/drafts/{id}/publish       Approver only (Req 8)
  POST  /staff/drafts/{id}/reject        Approver only
Visitor:
  GET   /visitor/{visitor_id}/welcome    returning-visitor greeting with the last quote (Req 2)
"""

from __future__ import annotations

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field

from mira.auth import Permission, User, require
from mira.config import get_settings
from mira.content_admin.drafts import DraftStore, publish
from mira.tracing import trace_url
from mira.visitors import welcome

router = APIRouter()

# Role checks as reusable dependencies (401 without a valid key, 403 without the permission).
CanView = Annotated[User, Depends(require(Permission.VIEW_ENQUIRIES))]
CanEdit = Annotated[User, Depends(require(Permission.EDIT_ENQUIRIES))]
CanDraft = Annotated[User, Depends(require(Permission.CREATE_DRAFT))]
CanPublish = Annotated[User, Depends(require(Permission.PUBLISH_CONTENT))]

FollowUp = Literal["new", "contacted", "awaiting_traveller", "booked", "payment_failed", "booking_failed", "closed"]


def _mira():
    from mira.main import get_mira

    return get_mira()


_drafts: DraftStore | None = None
_drafter = None


def drafts() -> DraftStore:
    global _drafts
    if _drafts is None:
        _drafts = DraftStore(get_settings().mira_db_url)
    return _drafts


def drafter():
    global _drafter
    if _drafter is None:
        from mira.content_admin.agent import make_drafter

        _drafter = make_drafter(get_settings())
    return _drafter


# --------------------------------------------------------------------------- enquiries (Req 7)

def _enquiry_view(row: dict) -> dict:
    q = row["quote"]
    return {
        "id": row["id"], "created_at": row["created_at"], "status": row["status"],
        "needs_specialist": row["needs_specialist"], "reason": row["reason"],
        "tour_id": row["tour_id"], "tour_name": q.get("tour_name") or q.get("requested"),
        "start_date": q.get("start_date"), "adults": q.get("adults"), "children": q.get("children"),
        "infants": q.get("infants"),
        "price_usd": row["price_usd"], "deposit_usd": row["deposit_usd"],
        "cost_usd": row["cost_usd"], "gross_profit_pct": row["gross_profit_pct"],
        "cost_lines": q.get("cost_lines", []), "rates_version": q.get("rates_version"),
        "request": None if "tour_name" in q else q,
        "contact_name": row.get("contact_name"), "contact_email": row.get("contact_email"),
        "contact_phone": row.get("contact_phone"), "booking_ref": row.get("booking_ref"),
        "follow_up_status": row["follow_up_status"], "notes": row["notes"],
        "session_id": row["session_id"], "trace_id": row["trace_id"], "trace_url": trace_url(row["trace_id"]),
    }


class EnquiryUpdate(BaseModel):
    notes: str | None = Field(None, max_length=4000)
    follow_up_status: FollowUp | None = None


@router.get("/staff/me")
def me(user: CanView) -> dict:
    return {"name": user.name, "role": user.role.value,
            "can_publish": user.can(Permission.PUBLISH_CONTENT)}


@router.get("/staff/enquiries")
def list_enquiries(_: CanView) -> list[dict]:
    return [_enquiry_view(r) for r in _mira().deps.store.list(limit=500)]


@router.patch("/staff/enquiries/{enquiry_id}")
def update_enquiry(enquiry_id: str, body: EnquiryUpdate,
                   _: CanEdit) -> dict:
    row = _mira().deps.store.update_staff_fields(enquiry_id, body.notes, body.follow_up_status)
    if row is None:
        raise HTTPException(404, "Enquiry not found.")
    return _enquiry_view(row)


# --------------------------------------------------------------------------- content drafts (Req 8)

class DraftCommand(BaseModel):
    command: str = Field(min_length=5, max_length=500)


def _draft_view(row: dict) -> dict:
    return {k: row[k] for k in ("id", "tour_id", "command", "title", "markdown", "staff_notes", "status",
                                "created_by", "created_at", "decided_by", "decided_at")} | {
        "trace_url": trace_url(row["trace_id"])}


@router.get("/staff/drafts")
def list_drafts(_: CanDraft) -> list[dict]:
    return [_draft_view(r) for r in drafts().list()]


@router.post("/staff/drafts")
def create_draft(body: DraftCommand, user: CanDraft) -> dict:
    from mira.content_admin.agent import create_draft as run_agent
    from mira.data.content import load_all_content

    s = get_settings()
    mira = _mira()
    docs = load_all_content(s)
    row = run_agent(
        body.command, user, drafter(), mira.deps.index, drafts(),
        existing_tour_ids={d.id for d in docs if d.type == "tour"},
        known_destinations={d.path.stem for d in docs if d.type == "destination" and d.status == "published"},
        today=s.mira_today, public_key=s.langfuse_public_key,
    )
    return _draft_view(row)


@router.post("/staff/drafts/{draft_id}/publish")
def publish_draft(draft_id: str, user: CanPublish) -> dict:
    s = get_settings()
    try:
        row = publish(drafts(), draft_id, user.name, s.mira_published_dir, s.mira_today)
    except KeyError:
        raise HTTPException(404, "Draft not found.") from None
    except ValueError as e:
        raise HTTPException(409, str(e)) from None
    _mira().refresh_content()
    return _draft_view(row)


@router.post("/staff/drafts/{draft_id}/reject")
def reject_draft(draft_id: str, user: CanPublish) -> dict:
    row = drafts().get(draft_id)
    if row is None:
        raise HTTPException(404, "Draft not found.")
    if row["status"] != "draft":
        raise HTTPException(409, f"{draft_id} is already {row['status']}")
    return _draft_view(drafts().decide(draft_id, "rejected", user.name))


# --------------------------------------------------------------------------- returning visitors (Req 2)

@router.get("/visitor/{visitor_id}/welcome")
def visitor_welcome(visitor_id: str) -> dict:
    mira = _mira()
    return welcome(visitor_id, mira.visitors, mira.deps.store, mira.deps.engine, mira.deps.tours,
                   get_settings().mira_today)
