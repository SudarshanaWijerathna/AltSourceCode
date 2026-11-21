"""Langfuse tracing (Python SDK v5).

- One trace per traveller turn (`traveller-turn`), one session per conversation.
- LangChain/LangGraph steps are captured by `langfuse.langchain.CallbackHandler`.
- Deterministic steps (pricing, price guard) are added as typed observations.
- Personal details are masked at export (`mask_otel_spans`) so they never leave the app.

Tracing is disabled automatically when Langfuse keys are not configured.
"""

from __future__ import annotations

import re
from functools import lru_cache

from langfuse import Langfuse
from langfuse.types import MaskOtelSpansParams, MaskOtelSpansResult, OtelSpanPatch

from mira.config import get_settings

_PATTERNS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+"), "[EMAIL]"),
    # card-like digit runs (13-19 digits with optional separators)
    (re.compile(r"\b(?:\d[ -]?){12,18}\d\b"), "[CARD]"),
    # phone numbers: +94 77 123 4567, 077-123-4567, (020) 7946 0958 ...
    (re.compile(r"(?<![\w-])\+?\(?\d{2,4}\)?[ .-]?\d{2,4}[ .-]?\d{3,4}(?:[ .-]?\d{2,4})?(?![\w-])"), "[PHONE]"),
    (re.compile(r"\b[A-Z]{1,2}\d{6,9}\b"), "[PASSPORT]"),
    # self-introductions: "my name is Jane Doe", "I'm called Raj"
    (re.compile(r"(?i)\b(my name is|i am called|i'm called|name:)\s+[A-Za-z][\w'-]*(?:\s+[A-Z][\w'-]*)?"), r"\1 [NAME]"),
]

_INTRO = re.compile(
    r"(?i)\b(?:my name is|i am called|i'm called|name:)\s+([A-Z][a-z'-]+(?:\s+[A-Z][a-z'-]+)?)"
)
_NOT_NAMES = {"a", "an", "the", "my", "our", "we", "for", "sri", "lanka"}


def introduced_names(text: str) -> list[str]:
    """Names a traveller introduces ('my name is Jane Doe') -> ['Jane Doe', 'Jane', 'Doe']."""
    names: list[str] = []
    for m in _INTRO.finditer(text):
        full = m.group(1).strip()
        parts = [p for p in full.split() if p.lower() not in _NOT_NAMES]
        if parts:
            names += [" ".join(parts), *parts]
    return sorted(set(names), key=len, reverse=True)


def scrub_names(reply: str, names: list[str]) -> str:
    """Remove introduced names from a reply ('Hello Jane.' -> 'Hello.')."""
    for name in names:
        reply = re.sub(rf",?\s*\b{re.escape(name)}\b", "", reply)
    return re.sub(r"\s+([.,!?])", r"\1", reply).strip()


# ISO dates (2027-01-10) look like phone numbers to the phone pattern; protect them.
_ISO_DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")


def redact(text: str) -> str:
    """Mask personal details in free text. Dates and prices are left intact."""
    protected: dict[str, str] = {}

    def _protect(m: re.Match[str]) -> str:
        key = f"\x00{len(protected)}\x00"
        protected[key] = m.group(0)
        return key

    out = _ISO_DATE.sub(_protect, text)
    for pattern, repl in _PATTERNS:
        out = pattern.sub(repl, out)
    for key, value in protected.items():
        out = out.replace(key, value)
    return out


def _mask_otel_spans(*, params: MaskOtelSpansParams) -> MaskOtelSpansResult | None:
    patches = {}
    for identifier, span in params.spans.items():
        changes = {}
        for key, value in span.attributes.items():
            if isinstance(value, str):
                masked = redact(value)
                if masked != value:
                    changes[key] = masked
        if changes:
            patches[identifier] = OtelSpanPatch(set_attributes=changes)
    return MaskOtelSpansResult(span_patches=patches) if patches else None


@lru_cache
def get_langfuse() -> Langfuse:
    s = get_settings()
    enabled = tracing_enabled()
    return Langfuse(
        public_key=s.langfuse_public_key,
        secret_key=s.langfuse_secret_key,
        base_url=s.langfuse_host,
        tracing_enabled=enabled,
        environment=s.mira_environment,
        mask_otel_spans=_mask_otel_spans,
    )


def tracing_enabled() -> bool:
    s = get_settings()
    return s.mira_tracing and bool(s.langfuse_public_key and s.langfuse_secret_key)


def trace_url(trace_id: str | None) -> str | None:
    if not trace_id or not tracing_enabled():
        return None
    try:
        return get_langfuse().get_trace_url(trace_id=trace_id)
    except Exception:  # noqa: BLE001 - tracing must never break a traveller turn
        return None
