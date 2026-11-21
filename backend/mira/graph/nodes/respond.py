"""Respond node: the LLM writes the words; code owns the numbers and the UI.

1. The responder LLM writes a reply from FACTS (which never contain staff data or prices).
2. Price guard (code): any money amount in the LLM text that is not the stored quote is a
   violation -> the reply is replaced by a safe template. Then the quoted price sentence is
   appended from the stored quote, so the only price a traveller sees came from the engine.
3. Every UI component is validated against the catalog; invalid ones are dropped.
"""

from __future__ import annotations

import json
import re
from decimal import Decimal

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from mira.graph.deps import Deps
from mira.graph.nodes.router import HISTORY
from mira.graph.prompts import INSTRUCTIONS, RESPONDER_SYSTEM
from mira.state import MiraState
from mira.tracing import get_langfuse, introduced_names, scrub_names
from mira.ui.catalog import validate_each

MONEY = re.compile(
    r"(?ix)"
    r"(?:usd|us\$|\$|lkr|rs\.?|€|£|eur|gbp)\s*\d[\d,]*(?:\.\d+)?"      # USD 315, $315, LKR 66,000
    r"|\d[\d,]*(?:\.\d+)?\s*(?:usd|dollars?|lkr|rupees?|euros?|pounds?)\b"  # 315 USD, 300 dollars
    r"|\b\d{1,3}\s*%\s*(?:off|discount)"                                   # 50% off
)

FALLBACK = {
    "greeting": "Hello, I'm Mira from Ceylon Compass Holidays. I can help you find, price and book "
                "tours in Sri Lanka. Are you thinking of a day tour or a longer trip, and who is travelling?",
    "ask": "Thanks. Could you tell me {slot}?",
    "suggest_tours": "These are our closest existing tours. I can price one of them for you, or pass "
                     "your request to our travel team to plan a custom trip.",
    "quote": "Here is your price for {title}.",
    "handoff": "I can't confirm a price for this online right now. A travel specialist will check it "
               "and confirm the price with you.",
    "unknown_tour": "We don't have that in our catalogue. I can pass your request to our team to see "
                    "if we can arrange it.",
    "no_content": "I don't have that information in our tour pages. I can pass your question to our "
                  "team and they will get back to you.",
    "off_topic": "I can only help with travel in Sri Lanka with Ceylon Compass. Shall we plan a trip?",
    "manipulation": "I can't change our prices or offer discounts, but I'm happy to give you a normal "
                    "quote for any of our tours.",
    "invalid_date": "That date has already passed. What start date would you like instead?",
    "answer": "I can't share prices from our tour pages, but I can work out an exact quote for your "
              "dates and group. Which tour and dates are you thinking of?",
}


def _usd(value) -> str:
    d = Decimal(str(value))
    return f"USD {d:,.0f}" if d == d.to_integral() else f"USD {d:,.2f}"


def price_sentence(q: dict) -> str:
    party = [f"{q['adults']} adult{'s' if q['adults'] != 1 else ''}"]
    if q.get("children"):
        party.append(f"{q['children']} child{'ren' if q['children'] != 1 else ''}")
    if q.get("infants"):
        party.append(f"{q['infants']} infant{'s' if q['infants'] != 1 else ''} (free)")
    text = f"Total price for {', '.join(party)}: {_usd(q['price_usd'])}."
    if Decimal(str(q["deposit_usd"])) == Decimal(str(q["price_usd"])):
        text += " Payable in full when you book."
    else:
        text += f" Deposit to book: {_usd(q['deposit_usd'])}. Balance {_usd(q['balance_usd'])} due by {q['balance_due']}."
    return text


def facts_for(state: MiraState) -> dict:
    facts = dict(state.get("facts") or {})
    if not facts:
        facts = {"kind": state["analysis"]["intent"]}
        if facts["kind"] not in INSTRUCTIONS:
            facts["kind"] = "greeting"
    instruction = INSTRUCTIONS[facts["kind"]].format(slot=facts.get("slot", ""))
    if facts.get("also"):
        instruction = f"{facts['also']} Then: {instruction}"
    facts["instruction"] = instruction
    return facts


def _number(mention: str) -> str:
    return re.sub(r"[^\d.]", "", mention).rstrip(".").removesuffix(".00")


def guard_reply(text: str, facts: dict) -> tuple[str, list[str]]:
    """Return (safe_text, violations). The LLM must not write any money amount, except figures
    quoted from a cited policy passage (facts["allowed_amounts"], e.g. an admin fee)."""
    allowed = set(facts.get("allowed_amounts", []))
    violations = [
        m.group(0) for m in MONEY.finditer(text)
        if "%" in m.group(0) or _number(m.group(0)) not in allowed
    ]
    if not text.strip() or violations:
        tour = (facts.get("tour") or {}).get("title", "this tour")
        return FALLBACK[facts["kind"]].format(slot=facts.get("slot", "a little more"), title=tour), violations
    return text.strip(), []


def make(deps: Deps):
    def run(state: MiraState) -> dict:
        facts = facts_for(state)
        if facts.get("final_text"):  # grounded answer already written from content
            draft = facts["final_text"]
        else:
            system = RESPONDER_SYSTEM.format(today=state["today"], facts=json.dumps(facts, indent=1, default=str))
            draft = deps.write([SystemMessage(system), *state["messages"][-HISTORY:]])

        lf = get_langfuse()
        with lf.start_as_current_observation(
            as_type="guardrail", name="check-price-mentions", input={"draft": draft, "kind": facts["kind"]},
        ) as g:
            reply, violations = guard_reply(draft, facts)
            names = introduced_names(
                " ".join(m.content for m in state["messages"] if isinstance(m, HumanMessage))
            )
            scrubbed = scrub_names(reply, names)
            g.update(output={"passed": not violations, "violations": violations,
                             "names_removed": scrubbed != reply},
                     level="WARNING" if violations else "DEFAULT")
            reply = scrubbed
        if state.get("quote"):
            reply = f"{reply}\n\n{price_sentence(state['quote'])}"
        if facts.get("sources") and not violations:
            reply = f"{reply}\n\nSource: " + "; ".join(
                f"{s['title']} ({s['source_path'].split('content/')[-1]})" for s in facts["sources"]
            )

        with lf.start_as_current_observation(
            as_type="guardrail", name="validate-ui-components", input=state.get("ui", []),
        ) as g:
            ui, errors = validate_each(state.get("ui", []))
            g.update(output={"valid": len(ui), "rejected": errors},
                     level="WARNING" if errors else "DEFAULT")

        return {"reply": reply, "ui": ui, "messages": [AIMessage(reply)]}

    return run
