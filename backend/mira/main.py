"""FastAPI entrypoint.

- POST /agent    AG-UI endpoint used by CopilotKit (generative UI, mira/agui.py)
- POST /chat     plain JSON turn (CLI-free smoke tests); same agent, same tracing
- POST /booking  mock booking + payment from the booking form (mira/booking.py)
Responses never contain staff-only fields.
"""

from __future__ import annotations

import uuid
from functools import lru_cache

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from mira.agui import router as agui_router
from mira.booking import BookingRequest, BookingResult, book
from mira.config import get_settings

app = FastAPI(title="Mira API", version="0.2.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(agui_router)


@lru_cache
def get_mira():
    from mira.agent import Mira

    return Mira()


class ChatIn(BaseModel):
    message: str = Field(min_length=1, max_length=4000)
    session_id: str | None = Field(None, max_length=100)


class ChatOut(BaseModel):
    session_id: str
    reply: str
    ui: list[dict]
    quote: dict | None
    needs_specialist: bool
    trace_id: str | None


@app.get("/health")
def health() -> dict:
    s = get_settings()
    return {"status": "ok", "today": s.mira_today.isoformat()}


@app.post("/chat", response_model=ChatOut)
def chat(body: ChatIn) -> ChatOut:
    session_id = body.session_id or f"web-{uuid.uuid4().hex[:12]}"
    r = get_mira().turn(session_id, body.message, tags=["web"])
    return ChatOut(
        session_id=session_id, reply=r.reply, ui=r.ui, quote=r.quote,
        needs_specialist=r.needs_specialist, trace_id=r.trace_id,
    )


@app.post("/booking", response_model=BookingResult)
def booking(body: BookingRequest) -> BookingResult:
    return book(body, get_mira().deps.store)
