"""Content agent: turns a staff command into a draft tour page, grounded in published content.

  "Add a 5-day Hill Country tour using the Ella photos"
    -> retrieve passages (published pages only) -> LLM DraftTour (structured) -> code validation
    -> stored as a DRAFT. It cannot publish: publishing is a separate, Approver-only endpoint.

The dataset contains no photos, so commands that reference images get a note for the approver
instead of invented assets (brand rule: no photos we do not have rights to).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date

from langchain_core.messages import HumanMessage, SystemMessage
from langfuse import propagate_attributes
from langfuse.langchain import CallbackHandler

from mira.auth import User
from mira.content_admin.drafts import (
    CATEGORIES,
    DraftStore,
    DraftTour,
    render_markdown,
    validate_draft,
)
from mira.retrieval import ContentIndex
from mira.tracing import get_langfuse

DRAFT_SYSTEM = """You write draft tour pages for Ceylon Compass Holidays, a Sri Lankan tour company.
A staff member gives you a command. Build the draft ONLY from the numbered passages, which come
from our published tour, destination and policy pages.

Rules:
- Use only places, activities, hotels and inclusions that appear in the passages. Do not add facts
  from general knowledge. If something the command asks for is not in the passages, leave it out
  and explain it in notes_for_staff.
- Never write prices, discounts or deposits.
- Our image library is not part of these passages. If the command mentions photos or images, say
  in notes_for_staff that no licensed photos were found and the approver must add them.
- category must be one of: {categories}.
- Plain English, short sentences, warm but not gushing, no exclamation marks.
- Cite the passage numbers you used.

PASSAGES:
{passages}
"""

Drafter = Callable[[list, list], DraftTour]   # (messages, langchain callbacks) -> draft


def make_drafter(settings) -> Drafter:
    from mira.llm import chat_model

    model = chat_model(settings, settings.mira_model_large, name="draft-tour-page", temperature=0.3)
    structured = model.with_structured_output(DraftTour)
    return lambda messages, callbacks: structured.invoke(
        messages, config={"run_name": "write-draft", "callbacks": callbacks})


def create_draft(command: str, user: User, drafter: Drafter, index: ContentIndex, store: DraftStore,
                 existing_tour_ids: set[str], known_destinations: set[str], today: date,
                 public_key: str | None = None) -> dict:
    from mira.graph.nodes.answer import format_passages

    lf = get_langfuse()
    with lf.start_as_current_observation(as_type="agent", name="draft-content", input={"command": command}) as root, \
            propagate_attributes(trace_name="staff-content-draft", user_id=f"staff:{user.name}",
                                 tags=["staff", "content-draft"]):
        with lf.start_as_current_observation(as_type="retriever", name="retrieve-content",
                                             input={"query": command}) as r:
            hits = index.search(command, k=10, min_score=0.5)
            r.update(output=[{"id": h.chunk.id, "score": h.score} for h in hits])
        passages = format_passages(hits)
        draft = drafter(
            [SystemMessage(DRAFT_SYSTEM.format(categories=", ".join(CATEGORIES),
                                               passages=passages or "(no passages found)")),
             HumanMessage(command)],
            [CallbackHandler(public_key=public_key)],
        )
        cited = [n for n in draft.citations if 1 <= n <= len(hits)]
        draft, notes = validate_draft(draft, passages, known_destinations)
        if not cited:
            notes.insert(0, "The draft cites none of our pages: check every fact before publishing.")
        if draft.notes_for_staff:
            notes.insert(0, draft.notes_for_staff)
        tour_id = store.next_tour_id(existing_tour_ids)
        markdown = render_markdown(tour_id, draft, "draft", today)
        row = store.create(tour_id, command, draft, markdown, notes, user.name, root.trace_id)
        root.update(output={"draft_id": row["id"], "tour_id": tour_id, "title": draft.title,
                            "notes": notes})
        return row
