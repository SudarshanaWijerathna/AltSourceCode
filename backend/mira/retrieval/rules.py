"""Content precedence rules: newer policy pages replace statements on older tour pages.

Both policies say so explicitly:
- P02 Cancellation policy: "applies to all bookings made from 1 November 2026. It replaces any
  cancellation terms shown on older pages."
- P03 Children and infants: "replaces any older family offers shown on individual tour pages."

Superseded lines are removed from tour chunks before anything reaches the LLM, and the
replacing policy is retrieved in their place. Each removal is recorded for the trace.
"""

from __future__ import annotations

import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Supersession:
    policy_id: str
    reason: str
    heading: re.Pattern[str] | None = None   # whole section superseded if its heading matches
    line: re.Pattern[str] | None = None      # individual lines superseded if they match


SUPERSESSIONS: tuple[Supersession, ...] = (
    Supersession(
        policy_id="P02",
        reason="Cancellation policy P02 replaces cancellation terms on older pages.",
        heading=re.compile(r"cancel", re.IGNORECASE),
        line=re.compile(r"\bcancel", re.IGNORECASE),
    ),
    Supersession(
        policy_id="P03",
        reason="Children and infants policy P03 replaces older family offers on tour pages.",
        line=re.compile(r"(?i)(kids?|child|children|famil\w*).{0,40}\b(free|offer|discount)"
                        r"|\b(free|offer|discount)\b.{0,40}(kids?|child|children)"),
    ),
)
