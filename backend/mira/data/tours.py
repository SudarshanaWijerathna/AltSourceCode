"""Published tour catalog built from content/tours/*.md (drafts are excluded)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from mira.config import get_settings
from mira.data.content import ContentDoc, load_content


@dataclass(frozen=True)
class TourInfo:
    id: str
    title: str
    category: str
    duration: str
    destinations: tuple[str, ...]
    summary: str
    source_path: str  # repo-relative, shown to travellers as the source

    @property
    def is_day_tour(self) -> bool:
        return "night" not in self.duration.lower()


def _summary(body: str) -> str:
    """First prose paragraph of the page (skips headings, bold offer lines and lists)."""
    for block in re.split(r"\n\s*\n", body):
        text = block.strip()
        if not text or text.startswith(("#", "-", "*", "|", ">")):
            continue
        return re.sub(r"\s+", " ", text)
    return ""


def _to_info(doc: ContentDoc, root) -> TourInfo:
    meta = doc.meta
    return TourInfo(
        id=doc.id,
        title=doc.title,
        category=str(meta.get("category", "")),
        duration=str(meta.get("duration", "")),
        destinations=tuple(meta.get("destinations") or ()),
        summary=_summary(doc.body),
        source_path=doc.path.relative_to(root).as_posix(),
    )


@lru_cache
def published_tours() -> dict[str, TourInfo]:
    s = get_settings()
    root = s.dataset_dir.parents[1]
    return {
        doc.id: _to_info(doc, root)
        for doc in load_content(s.content_dir)
        if doc.type == "tour" and doc.status == "published"
    }


def catalog_for_prompt() -> str:
    """Compact list the router uses to map what the traveller said to a tour id."""
    lines = [
        f"- {t.id}: {t.title} | {t.category} | {t.duration} | destinations: {', '.join(t.destinations)}"
        for t in published_tours().values()
    ]
    return "\n".join(lines)
