"""Chat with Mira in the terminal: `npm run chat` (or `python -m mira.cli`).

Shows the reply, the UI components Mira chose, the saved enquiry and the trace link.
"""

from __future__ import annotations

import json
import sys
import uuid

from mira.agent import Mira
from mira.tracing import get_langfuse


def main() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    mira = Mira()
    session_id = f"cli-{uuid.uuid4().hex[:8]}"
    print(f"Mira (session {session_id}, today={mira.settings.mira_today}). Ctrl+C or 'exit' to quit.\n")
    try:
        while True:
            message = input("you> ").strip()
            if message.lower() in {"exit", "quit"}:
                break
            if not message:
                continue
            r = mira.turn(session_id, message, tags=["cli"])
            print(f"\nmira> {r.reply}\n")
            for c in r.ui:
                print(f"  [ui] {c['component']}: " + json.dumps({k: v for k, v in c.items() if k != 'component'})[:160])
            meta = {"route": r.route, "enquiry": r.enquiry_id, "flagged": r.needs_specialist}
            print(f"  [meta] {json.dumps(meta)}")
            if r.trace_url:
                print(f"  [trace] {r.trace_url}")
            print()
    except (KeyboardInterrupt, EOFError):
        pass
    finally:
        get_langfuse().flush()


if __name__ == "__main__":
    main()
