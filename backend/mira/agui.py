"""AG-UI endpoint for CopilotKit (Req 3: generative UI).

One AG-UI run = one Mira turn (one Langfuse trace). The reply streams as an assistant text
message; each UI component Mira chose becomes a *backend tool call* named `show_<component>`
whose arguments are the component payload. The frontend renders those calls with
`useRenderTool` (CopilotKit "tool call rendering"). Nothing executes in the browser.

Every component is validated against the catalog (mira/ui/catalog.py) here, immediately before
it is encoded; invalid ones are dropped and never reach the browser.
"""

from __future__ import annotations

import json
import logging
import uuid
from collections.abc import AsyncIterator

from ag_ui.core import (
    EventType,
    RunAgentInput,
    RunFinishedEvent,
    RunStartedEvent,
    TextMessageContentEvent,
    TextMessageEndEvent,
    TextMessageStartEvent,
    ToolCallArgsEvent,
    ToolCallEndEvent,
    ToolCallResultEvent,
    ToolCallStartEvent,
)
from ag_ui.encoder import EventEncoder
from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse
from starlette.concurrency import run_in_threadpool

from mira.ui.catalog import validate_each
from mira.visitors import visitor_from_thread

log = logging.getLogger(__name__)
router = APIRouter()

TOOL_PREFIX = "show_"
CHUNK = 48  # characters per streamed text delta


def latest_user_text(run: RunAgentInput) -> str:
    for message in reversed(run.messages):
        if getattr(message, "role", None) != "user":
            continue
        content = message.content
        if isinstance(content, str):
            return content.strip()
        parts = [getattr(p, "text", "") for p in content or [] if getattr(p, "type", "") == "text"]
        return " ".join(parts).strip()
    return ""


def component_events(component: dict, parent_message_id: str) -> list:
    call_id = f"call_{uuid.uuid4().hex[:12]}"
    args = {k: v for k, v in component.items() if k != "component"}
    return [
        ToolCallStartEvent(type=EventType.TOOL_CALL_START, tool_call_id=call_id,
                           tool_call_name=TOOL_PREFIX + component["component"],
                           parent_message_id=parent_message_id),
        ToolCallArgsEvent(type=EventType.TOOL_CALL_ARGS, tool_call_id=call_id, delta=json.dumps(args)),
        ToolCallEndEvent(type=EventType.TOOL_CALL_END, tool_call_id=call_id),
        ToolCallResultEvent(type=EventType.TOOL_CALL_RESULT, message_id=f"msg_{uuid.uuid4().hex[:12]}",
                            tool_call_id=call_id, content="shown", role="tool"),
    ]


def turn_events(run: RunAgentInput, reply: str, ui: list[dict]) -> list:
    """All events for one run, in order (pure function: easy to test)."""
    message_id = f"msg_{uuid.uuid4().hex[:12]}"
    events: list = [
        RunStartedEvent(type=EventType.RUN_STARTED, thread_id=run.thread_id, run_id=run.run_id),
        TextMessageStartEvent(type=EventType.TEXT_MESSAGE_START, message_id=message_id, role="assistant"),
    ]
    events += [
        TextMessageContentEvent(type=EventType.TEXT_MESSAGE_CONTENT, message_id=message_id, delta=reply[i:i + CHUNK])
        for i in range(0, len(reply), CHUNK)
    ]
    events.append(TextMessageEndEvent(type=EventType.TEXT_MESSAGE_END, message_id=message_id))

    valid, errors = validate_each(ui)
    if errors:
        log.warning("dropped invalid UI components before sending: %s", errors)
    for component in valid:
        events += component_events(component, message_id)
    events.append(RunFinishedEvent(type=EventType.RUN_FINISHED, thread_id=run.thread_id, run_id=run.run_id))
    return events


@router.post("/agent")
async def agent_endpoint(run: RunAgentInput, request: Request) -> StreamingResponse:
    from mira.main import get_mira

    encoder = EventEncoder(accept=request.headers.get("accept"))
    message = latest_user_text(run)

    async def stream() -> AsyncIterator[str]:
        if not message:
            reply, ui = ("Hello, I'm Mira from Ceylon Compass Holidays. Are you after a day tour or "
                         "a longer trip?"), []
        else:
            visitor = visitor_from_thread(run.thread_id)
            result = await run_in_threadpool(get_mira().turn, run.thread_id, message, ["web"], visitor)
            reply, ui = result.reply, result.ui
        for event in turn_events(run, reply, ui):
            yield encoder.encode(event)

    return StreamingResponse(stream(), media_type=encoder.get_content_type())
