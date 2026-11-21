"""Chunking and BM25 retrieval over published content.

- Only `status: published` pages are indexed (drafts never reach Mira).
- Pages are split at headings; each tour also gets an overview chunk from its front matter.
- Teaser prices and other money amounts on tour/destination pages are removed: prices come
  only from the rate workbook. Policy amounts (e.g. an admin fee) are policy facts and kept.
- Lines superseded by newer policies (rules.py) are removed and the policy is added instead.
"""

from __future__ import annotations

import math
import re
from collections import Counter
from dataclasses import dataclass, field
from functools import lru_cache

from mira.config import get_settings
from mira.data.content import ContentDoc, load_content
from mira.retrieval.rules import SUPERSESSIONS

_MONEY = re.compile(
    r"(?i)(?:from\s+)?(?:usd|us\$|\$|lkr|rs\.?)\s*\d[\d,]*(?:\.\d+)?(?:\s*per\s+\w+)?"
    r"|\bsave\s+\d{1,3}\s*%|\b\d{1,3}\s*%\s*(?:off|discount)"
)
_TOKEN = re.compile(r"[a-z0-9]+")
_STOP = {
    "a", "an", "and", "are", "as", "at", "be", "by", "can", "do", "does", "for", "from", "has",
    "have", "how", "i", "in", "is", "it", "its", "me", "my", "of", "on", "or", "our", "the",
    "their", "there", "this", "to", "tour", "tours", "we", "what", "when", "where", "which", "who",
    "will", "with", "you", "your", "about", "any", "was", "were", "tell",
}


def tokenize(text: str) -> list[str]:
    out = []
    for tok in _TOKEN.findall(text.lower()):
        if tok in _STOP:
            continue
        if len(tok) > 4 and tok.endswith("s") and not tok.endswith("ss"):
            tok = tok[:-1]  # crude plural folding: leopards -> leopard
        out.append(tok)
    return out


@dataclass(frozen=True)
class Chunk:
    id: str              # e.g. "T07#day-2-kandy-city-tour"
    doc_id: str
    doc_type: str        # tour | destination | policy | faq | about | testimonials ...
    title: str           # page title
    heading: str         # section heading ("" for the intro)
    text: str
    source_path: str     # repo-relative path shown to the traveller
    last_updated: str
    superseded: tuple[str, ...] = ()   # reasons for lines removed from this chunk


@dataclass(frozen=True)
class Hit:
    chunk: Chunk
    score: float
    why: str = "bm25"    # bm25 | supersession | focus


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-") or "intro"


def _clean(doc: ContentDoc, text: str) -> str:
    if doc.type in ("tour", "destination"):
        text = _MONEY.sub("", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _apply_supersessions(doc: ContentDoc, heading: str, text: str) -> tuple[str | None, tuple[str, ...]]:
    """Return (text without superseded lines or None if the whole section goes, reasons)."""
    if doc.type != "tour":
        return text, ()
    reasons: list[str] = []
    for rule in SUPERSESSIONS:
        if rule.heading and rule.heading.search(heading):
            return None, (rule.reason,)
    kept = []
    for line in text.splitlines():
        rule = next((r for r in SUPERSESSIONS if r.line and r.line.search(line)), None)
        if rule:
            reasons.append(rule.reason)
        else:
            kept.append(line)
    return "\n".join(kept), tuple(sorted(set(reasons)))


def chunk_doc(doc: ContentDoc, root) -> list[Chunk]:
    source = doc.path.relative_to(root).as_posix()
    updated = str(doc.meta.get("last_updated", ""))
    sections: list[tuple[str, list[str]]] = [("", [])]
    for line in doc.body.splitlines():
        m = re.match(r"^(#{1,3})\s+(.*)", line)
        if not m:
            sections[-1][1].append(line)
            continue
        is_page_title = len(m.group(1)) == 1 and len(sections) == 1 and not "".join(sections[0][1]).strip()
        if not is_page_title:  # the H1 page title is already the chunk title
            sections.append((m.group(2).strip(), []))

    chunks: list[Chunk] = []
    if doc.type == "tour":
        meta = doc.meta
        facts = [
            f"{doc.title}.",
            f"Category: {meta.get('category', '')}.",
            f"Duration: {meta.get('duration', '')}.",
            f"Starts: {meta.get('start', '')}." if meta.get("start") else "",
            f"Destinations: {', '.join(meta.get('destinations') or [])}.",
            f"Hotels: {', '.join(meta.get('hotels') or [])}." if meta.get("hotels") else "",
        ]
        chunks.append(Chunk(
            id=f"{doc.id}#overview", doc_id=doc.id, doc_type=doc.type, title=doc.title,
            heading="Overview", text=" ".join(f for f in facts if f), source_path=source,
            last_updated=updated,
        ))
    for heading, lines in sections:
        raw = "\n".join(lines).strip()
        if not raw:
            continue
        text, reasons = _apply_supersessions(doc, heading, raw)
        if text is None:
            chunks.append(Chunk(
                id=f"{doc.id}#{_slug(heading)}", doc_id=doc.id, doc_type=doc.type, title=doc.title,
                heading=heading, text="", source_path=source, last_updated=updated, superseded=reasons,
            ))
            continue
        text = _clean(doc, text)
        if text or reasons:
            chunks.append(Chunk(
                id=f"{doc.id}#{_slug(heading)}", doc_id=doc.id, doc_type=doc.type, title=doc.title,
                heading=heading, text=text, source_path=source, last_updated=updated, superseded=reasons,
            ))
    return chunks


@dataclass
class ContentIndex:
    chunks: list[Chunk]
    k1: float = 1.5
    b: float = 0.75
    _tf: list[Counter] = field(default_factory=list, init=False, repr=False)
    _df: Counter = field(default_factory=Counter, init=False, repr=False)
    _avg: float = field(default=0.0, init=False, repr=False)

    def __post_init__(self) -> None:
        for c in self.chunks:
            # title and heading are part of what a chunk is "about"
            tf = Counter(tokenize(f"{c.title} {c.heading} {c.heading} {c.text}"))
            self._tf.append(tf)
            self._df.update(tf.keys())
        self._avg = sum(sum(t.values()) for t in self._tf) / max(len(self._tf), 1)
        self.by_id = {c.id: c for c in self.chunks}

    def _bm25(self, q: list[str], i: int) -> float:
        tf, n = self._tf[i], len(self.chunks)
        length = sum(tf.values())
        score = 0.0
        for term in set(q):
            if term not in tf:
                continue
            idf = math.log(1 + (n - self._df[term] + 0.5) / (self._df[term] + 0.5))
            f = tf[term]
            score += idf * f * (self.k1 + 1) / (f + self.k1 * (1 - self.b + self.b * length / self._avg))
        return score

    def search(self, query: str, k: int = 6, focus_doc: str | None = None,
               min_score: float = 1.0) -> list[Hit]:
        q = tokenize(query)
        if not q:
            return []
        scored: list[Hit] = []
        for i, c in enumerate(self.chunks):
            s = self._bm25(q, i)
            if focus_doc and c.doc_id == focus_doc and s > 0:
                s += 1.5
            if s >= min_score:
                scored.append(Hit(c, round(s, 3)))
        scored.sort(key=lambda h: (-h.score, h.chunk.id))
        hits = scored[:k]

        # Superseded lines were dropped; bring in the policy that replaces them.
        have = {h.chunk.id for h in hits}
        for h in list(hits):
            for reason in h.chunk.superseded:
                rule = next(r for r in SUPERSESSIONS if r.reason == reason)
                for pc in self.chunks:
                    if pc.doc_id == rule.policy_id and pc.text and pc.id not in have:
                        hits.append(Hit(pc, h.score, why="supersession"))
                        have.add(pc.id)
        return [h for h in hits if h.chunk.text]


@lru_cache
def get_index() -> ContentIndex:
    s = get_settings()
    root = s.dataset_dir.parents[1]
    chunks: list[Chunk] = []
    for doc in load_content(s.content_dir):
        if doc.status == "published":
            chunks += chunk_doc(doc, root)
    return ContentIndex(chunks)
