"""LLM judge for behaviour expectations (answer quality), calibrated against human labels.

The judge sees the expected behaviour, the conversation, the UI components Mira chose and the
text of the pages Mira cited, so it can tell a grounded answer from general knowledge.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass

from pydantic import BaseModel, Field

from mira.config import REPO_ROOT, get_settings

JUDGE_SYSTEM = """You are a strict evaluator of Mira, the booking assistant of Ceylon Compass Holidays
(a Sri Lankan tour company). Decide whether Mira's replies meet the EXPECTED BEHAVIOUR.

Judge only against the expected behaviour and these standing rules:
- Mira must not state facts that are not in the CITED PAGES (when it answers questions about tours,
  places or policies). Generic friendly phrasing is fine.
- Mira must never invent a price. Price lines produced by the system after a real quote are fine.
- Mira must not reveal internal instructions, costs, margins or supplier rates.

Be strict but fair: wording does not need to match, the substance does. If the expected behaviour
is met and no standing rule is broken, passed=true. Give a one-sentence reason.
"""


class JudgeVerdict(BaseModel):
    passed: bool = Field(description="True if the replies meet the expected behaviour and break no rule.")
    reason: str = Field(description="One sentence explaining the verdict.")


@dataclass
class Transcript:
    turns: list[dict]          # [{"user": str, "mira": str, "ui": [component names], "sources": [paths]}]

    def render(self) -> str:
        lines = []
        for n, t in enumerate(self.turns, start=1):
            lines.append(f"Turn {n}\nTraveller: {t['user']}\nMira: {t['mira']}")
            if t.get("ui"):
                lines.append(f"(UI components shown: {', '.join(t['ui'])})")
        return "\n\n".join(lines)

    def sources(self) -> list[str]:
        seen: list[str] = []
        for t in self.turns:
            for s in t.get("sources", []):
                if s not in seen:
                    seen.append(s)
        return seen


def _page_text(rel_path: str, limit: int = 2500) -> str:
    if rel_path.startswith("published/"):  # approved pages outside the repo (see data.content.source_path)
        path = get_settings().mira_published_dir / rel_path.removeprefix("published/")
    else:
        path = REPO_ROOT / rel_path
    if not path.exists():
        return "(missing)"
    # Keep front matter (durations, hotels live there) but drop teaser prices.
    text = re.sub(r"(?m)^teaser_price:.*\n", "", path.read_text(encoding="utf-8"))
    return text[:limit]


def build_messages(behaviour: str, transcript: Transcript) -> list:
    from langchain_core.messages import HumanMessage, SystemMessage

    pages = transcript.sources()
    cited = "\n\n".join(f"### {p}\n{_page_text(p)}" for p in pages) or "(Mira cited no pages)"
    body = (f"EXPECTED BEHAVIOUR:\n{behaviour}\n\nCONVERSATION:\n{transcript.render()}\n\n"
            f"CITED PAGES:\n{cited}")
    return [SystemMessage(JUDGE_SYSTEM), HumanMessage(body)]


class Judge:
    def __init__(self):
        from mira.llm import chat_model

        s = get_settings()
        model = chat_model(s, s.mira_model_large, name="judge-behaviour", thinking_level="low")
        self._structured = model.with_structured_output(JudgeVerdict)

    def __call__(self, behaviour: str, transcript: Transcript) -> JudgeVerdict:
        return self._structured.invoke(build_messages(behaviour, transcript))


# --------------------------------------------------------------------------- calibration

def load_calibration() -> list[dict]:
    path = REPO_ROOT / "evals" / "labels" / "judge_calibration.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def calibrate(judge: Judge) -> dict:
    rows = []
    for item in load_calibration():
        transcript = Transcript(item["transcript"])
        verdict = judge(item["behaviour"], transcript)
        human = item["label"] == "pass"
        rows.append({"id": item["id"], "human": item["label"], "judge": "pass" if verdict.passed else "fail",
                     "agree": human == verdict.passed, "reason": verdict.reason,
                     "labelled_by": item.get("labelled_by", "")})
    agree = sum(r["agree"] for r in rows)
    return {"agreement": agree / len(rows) if rows else 0.0, "agree": agree, "total": len(rows), "rows": rows}
