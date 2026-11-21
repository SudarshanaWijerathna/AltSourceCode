"""Published tour catalog built from content/tours/*.md (drafts are excluded)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
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
    days: tuple[tuple[int, str, str], ...] = field(default=())  # (day, title, description) from the page

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


_DAY = re.compile(r"^#{2,4}\s*Day\s+(\d+)\s*[:\-–]\s*(.+?)\s*$", re.MULTILINE)
_MONEY = re.compile(r"(?i)(?:from\s+)?(?:usd|us\$|\$|lkr|rs\.?)\s*\d[\d,]*(?:\.\d+)?(?:\s*per\s+\w+)?")


def _days(body: str) -> tuple[tuple[int, str, str], ...]:
    """'### Day 2: Kandy city tour' sections -> (2, 'Kandy city tour', text). Prices are removed."""
    matches = list(_DAY.finditer(body))
    out = []
    for i, m in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(body)
        section = re.split(r"\n## ", body[m.end():end])[0]  # stop at the next H2 (e.g. Inclusions)
        lines = [ln.strip().lstrip("-* ").replace("**", "") for ln in section.strip().splitlines() if ln.strip()]
        text = _MONEY.sub("", " · ".join(lines)).strip()
        out.append((int(m.group(1)), m.group(2), text[:500]))
    return tuple(out)


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
        days=_days(doc.body),
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
