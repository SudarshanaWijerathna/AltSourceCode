"""Mira: runs one traveller turn through the graph inside one Langfuse trace."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from langchain_core.messages import HumanMessage
from langfuse import propagate_attributes
from langfuse.langchain import CallbackHandler

from mira.config import Settings, get_settings
from mira.data.tours import catalog_for_prompt, published_tours
from mira.enquiries.store import EnquiryStore
from mira.graph.builder import build_graph
from mira.graph.deps import Deps
from mira.graph.ui import specialist_handoff
from mira.pricing import get_engine
from mira.tracing import get_langfuse, redact, trace_url

log = logging.getLogger(__name__)

SORRY = ("Sorry, something went wrong on my side. Please try again in a moment, or leave your "
         "details and our team will get back to you.")


@dataclass
class TurnResult:
    reply: str
    ui: list[dict] = field(default_factory=list)
    quote: dict | None = None
    enquiry_id: str | None = None
    needs_specialist: bool = False
    route: str | None = None
    trace_id: str | None = None
    trace_url: str | None = None
    error: str | None = None


def default_deps(settings: Settings | None = None) -> Deps:
    from mira.llm import make_analyzer, make_writer

    s = settings or get_settings()
    return Deps(
        analyze=make_analyzer(s),
        write=make_writer(s),
        engine=get_engine(),
        store=EnquiryStore(s.mira_db_url),
        tours=published_tours(),
        catalog_text=catalog_for_prompt(),
    )


class Mira:
    def __init__(self, deps: Deps | None = None, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.deps = deps or default_deps(self.settings)
        self.graph = build_graph(self.deps)

    def turn(self, session_id: str, message: str, tags: list[str] | None = None) -> TurnResult:
        lf = get_langfuse()
        with lf.start_as_current_observation(
            as_type="agent", name="mira-turn", input={"message": redact(message)},
        ) as root, propagate_attributes(
            session_id=session_id, trace_name="traveller-turn", tags=tags or ["traveller"],
            metadata={"today": self.settings.mira_today.isoformat()},
        ):
            trace_id = root.trace_id
            try:
                state = self.graph.invoke(
                    {
                        "messages": [HumanMessage(message)],
                        "session_id": session_id,
                        "trace_id": trace_id,
                        "today": self.settings.mira_today.isoformat(),
                    },
                    config={
                        "callbacks": [CallbackHandler(public_key=self.settings.langfuse_public_key)],
                        "configurable": {"thread_id": session_id},
                        "run_name": "mira-graph",
                    },
                )
            except Exception as exc:  # the traveller never sees an error page
                log.exception("turn failed")
                root.update(level="ERROR", status_message=str(exc)[:500], output={"reply": SORRY})
                return TurnResult(
                    reply=SORRY, ui=[specialist_handoff("Our team can help you directly.")],
                    trace_id=trace_id, trace_url=trace_url(trace_id), error=type(exc).__name__,
                )

            result = TurnResult(
                reply=state["reply"],
                ui=state.get("ui", []),
                quote=state.get("quote"),
                enquiry_id=state.get("enquiry_id"),
                needs_specialist=bool(state.get("needs_specialist")),
                route=(state.get("facts") or {}).get("kind"),
                trace_id=trace_id,
                trace_url=trace_url(trace_id),
            )
            root.update(
                output={"reply": result.reply, "ui": [c["component"] for c in result.ui]},
                metadata={"route": result.route, "enquiry_id": result.enquiry_id,
                          "needs_specialist": result.needs_specialist,
                          "profile": state.get("profile", {})},
            )
            return result
