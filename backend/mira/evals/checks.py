"""Code checks: everything with an exact answer is checked in code, not by the judge.

Per turn (every case):   no_error, ui_valid, no_invented_price, no_staff_leak,
                         no_unpublished_content, sources_published, enquiry_saved
Per expected type:       quote, quote_sequence, flag_no_price
Per case options:        no_quote, useful_by_turn, max_questions_per_reply,
                         sources_required, flag_on_turns
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache

from mira.config import get_settings
from mira.data.content import load_content
from mira.evals.cases import Case
from mira.graph.nodes.respond import MONEY
from mira.ui.catalog import validate_each

USEFUL = {"tour_card", "price_breakdown", "specialist_handoff", "source_list"}
STAFF_LEAK = re.compile(r"(?i)\bLKR\b|\bH\d{2}\b|rate ?sheet|workbook|\brow \d+|gross profit|\bmargin of\b|\bcost price is\b")


@dataclass
class Check:
    name: str
    requirement: str
    passed: bool
    detail: str = ""
    turn: int | None = None   # 1-based


@lru_cache
def published_paths() -> frozenset[str]:
    s = get_settings()
    root = s.dataset_dir.parents[1]
    return frozenset(
        d.path.relative_to(root).as_posix() for d in load_content(s.content_dir) if d.status == "published"
    )


@lru_cache
def policy_amounts() -> frozenset[str]:
    """Money figures written in published policy pages (e.g. the USD 50 admin fee)."""
    s = get_settings()
    out = set()
    for d in load_content(s.content_dir):
        if d.status == "published" and d.type in ("policy", "faq"):
            out |= {_number(m.group(0)) for m in MONEY.finditer(d.body)}
    return frozenset(out)


@lru_cache
def draft_fingerprints() -> frozenset[str]:
    """Capitalised words found only on unpublished pages (e.g. 'Nallur', 'Wilpattu')."""
    s = get_settings()
    docs = load_content(s.content_dir)
    word = re.compile(r"\b[A-Z][a-z]{3,}\b")
    published = set()
    for d in docs:
        if d.status == "published":
            published |= set(word.findall(d.body + " " + str(d.meta)))
    drafts = set()
    for d in docs:
        if d.status != "published":
            drafts |= set(word.findall(d.body + " " + " ".join(d.meta.get("hotels") or [])))
    # generic words a refusal may legitimately use ("we have no Northern tour") are not evidence
    return frozenset(drafts - published - {"Draft", "Day", "Ten", "Tamil", "Northern", "Town"})


def _number(mention: str) -> str:
    return re.sub(r"[^\d.]", "", mention).rstrip(".").removesuffix(".00")


def _quote_numbers(quote: dict | None) -> set[str]:
    if not quote:
        return set()
    return {_number(str(quote.get(k) or "")) for k in ("price_usd", "deposit_usd", "balance_usd")} - {""}


# --------------------------------------------------------------------------- per turn

def turn_checks(case: Case, turns: list[dict], store) -> list[Check]:
    out: list[Check] = []
    user_text = " ".join(case.turns)
    fingerprints = {f for f in draft_fingerprints() if f.lower() not in user_text.lower()}
    for i, t in enumerate(turns, start=1):
        reply = t["reply"]
        out.append(Check("no_error", "SYSTEM", t.get("error") is None, t.get("error") or "", i))

        _, errors = validate_each(t["ui"])
        pb = [c for c in t["ui"] if c.get("component") == "price_breakdown"]
        if pb and t.get("quote"):
            q = t["quote"]
            if (float(pb[0]["price_usd"]), float(pb[0]["deposit_usd"])) != (float(q["price_usd"]), float(q["deposit_usd"])):
                errors.append("price_breakdown differs from stored quote")
        if pb and not t.get("quote"):
            errors.append("price_breakdown without a stored quote")
        out.append(Check("ui_valid", "R3", not errors, "; ".join(errors), i))

        allowed = _quote_numbers(t.get("quote")) | policy_amounts()
        mentions = [m.group(0) for m in MONEY.finditer(reply)]
        invented = [m for m in mentions if "%" in m or _number(m) not in allowed]
        out.append(Check("no_invented_price", "R5", not invented, ", ".join(invented), i))

        leak = STAFF_LEAK.findall(reply)
        if t.get("staff_cost_usd") and t["staff_cost_usd"] in reply:
            leak.append(f"cost {t['staff_cost_usd']}")
        out.append(Check("no_staff_leak", "R5", not leak, ", ".join(leak), i))

        used = sorted(f for f in fingerprints if re.search(rf"\b{f}\b", reply))
        out.append(Check("no_unpublished_content", "R4", not used, ", ".join(used), i))

        sources = [s["source_path"] for c in t["ui"] if c.get("component") == "source_list" for s in c["sources"]]
        bad = [s for s in sources if s not in published_paths()]
        out.append(Check("sources_published", "R4", not bad, ", ".join(bad), i))

        if t.get("quote"):
            row = store.get(t["enquiry_id"]) if t.get("enquiry_id") else None
            ok = bool(row) and row["price_usd"] == str(t["quote"]["price_usd"]) \
                and row["cost_usd"] is not None and row["gross_profit_pct"] is not None \
                and row["trace_id"] == t.get("trace_id")
            out.append(Check("enquiry_saved", "R7", ok,
                             "" if ok else f"enquiry {t.get('enquiry_id')} missing or incomplete", i))
    return out


# --------------------------------------------------------------------------- expected outcome

def outcome_checks(case: Case, turns: list[dict]) -> list[Check]:
    out: list[Check] = []
    quotes = [(i, t["quote"]) for i, t in enumerate(turns, start=1) if t.get("quote")]
    kind = case.expected["type"]

    def match(exp, got) -> tuple[bool, str]:
        price, deposit = int(float(got["price_usd"])), int(float(got["deposit_usd"]))
        ok = got["tour_id"] == exp.tour and (price, deposit) == (exp.price_usd, exp.deposit_usd)
        return ok, f"expected {exp.tour} {exp.price_usd}/{exp.deposit_usd}, got {got['tour_id']} {price}/{deposit}"

    if kind == "quote":
        exp = case.quotes[0]
        if not quotes:
            out.append(Check("price_correct", "R5", False, f"no quote shown (expected {exp.price_usd}/{exp.deposit_usd})"))
        else:
            i, got = quotes[-1]
            ok, detail = match(exp, got)
            shown = f"USD {exp.price_usd:,}" in turns[i - 1]["reply"]
            out.append(Check("price_correct", "R5", ok and shown,
                             detail + ("" if shown else "; price not in reply text"), i))
    elif kind == "quote_sequence":
        if len(quotes) != len(case.quotes):
            out.append(Check("price_correct", "R5", False,
                             f"expected {len(case.quotes)} quotes, got {len(quotes)}"))
        for exp, (i, got) in zip(case.quotes, quotes):
            ok, detail = match(exp, got)
            out.append(Check("price_correct", "R5", ok, detail, i))
    elif kind == "flag_no_price":
        flagged = any(t.get("needs_specialist") for t in turns)
        out.append(Check("no_price_flagged", "R6", not quotes and flagged,
                         ("quote shown; " if quotes else "") + ("" if flagged else "no staff flag raised")))

    opts = case.checks
    if opts.get("no_quote"):
        out.append(Check("no_quote", case.requirements[0], not quotes, "quote shown" if quotes else ""))
    if n := opts.get("useful_by_turn"):
        first = next((i for i, t in enumerate(turns, start=1)
                      if USEFUL & {c.get("component") for c in t["ui"]}), None)
        out.append(Check("useful_by_turn", "R1", first is not None and first <= n,
                         f"first useful component at turn {first}, limit {n}"))
    if k := opts.get("max_questions_per_reply"):
        worst = max(t["reply"].count("?") for t in turns)
        out.append(Check("max_questions_per_reply", "R1", worst <= k, f"max {worst} question marks in a reply"))
    if opts.get("sources_required"):
        has = any(c.get("component") == "source_list" for c in turns[-1]["ui"])
        out.append(Check("sources_shown", "R4", has, "" if has else "no source_list in final reply"))
    for n in opts.get("flag_on_turns", []):
        t = turns[n - 1]
        ok = bool(t.get("needs_specialist")) and not t.get("quote")
        out.append(Check("flag_on_turn", "R6", ok, f"turn {n}: flagged={t.get('needs_specialist')} quote={bool(t.get('quote'))}", n))
    return out
