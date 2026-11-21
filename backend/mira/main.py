"""FastAPI entrypoint.

POST /chat is a plain JSON endpoint used by the CLI-free smoke tests and, until the AG-UI
bridge is added, by the frontend. Responses never contain staff-only fields.
"""

from __future__ import annotations

import uuid
from functools import lru_cache

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from mira.config import get_settings

app = FastAPI(title="Mira API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


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


# TODO: AG-UI / CopilotKit bridge at /agent; staff routes behind role checks.
