"""Markdown report: targets, pass rates per requirement, failures with trace links, judge agreement."""

from __future__ import annotations

from collections import defaultdict

from mira.evals.cases import REQUIREMENT_NAMES


def pct(n: int, d: int) -> str:
    return "n/a" if d == 0 else f"{100 * n / d:.0f}% ({n}/{d})"


def metrics(results: list[dict]) -> dict:
    checks = [c for r in results for c in r["checks"]]

    def count(name):
        sel = [c for c in checks if c["name"] == name]
        return sum(c["passed"] for c in sel), len(sel)

    flag_ok = [c for c in checks if c["name"] in ("no_price_flagged", "flag_on_turn")]
    return {
        "price_accuracy": count("price_correct"),
        "invented_price_turns": sum(1 for c in checks if c["name"] == "no_invented_price" and not c["passed"]),
        "missing_expired_handling": (sum(c["passed"] for c in flag_ok), len(flag_ok)),
        "ui_valid": count("ui_valid"),
        "staff_leak_free": count("no_staff_leak"),
        "unpublished_free": count("no_unpublished_content"),
        "enquiries_saved": count("enquiry_saved"),
        "errors": sum(1 for c in checks if c["name"] == "no_error" and not c["passed"]),
        "judge": count("judge"),
    }


def render(run: dict, results: list[dict], calibration: dict | None) -> str:
    m = metrics(results)
    passed = sum(r["passed"] for r in results)
    L: list[str] = []
    L.append(f"# Mira evaluation report — {run['label'] or run['run_id']}")
    L.append("")
    L.append(f"- Run: `{run['run_id']}` · git `{run['git']}` · {run['started']} · {run['duration_s']:.0f}s")
    L.append(f"- Today (configured): **{run['today']}** · model: `{run['model']}` · judge: `{run['judge_model']}`")
    L.append(f"- Rates: `{run['rates_version']}`")
    L.append(f"- Cases: **{len(results)}** ({run['seed_cases']} seed from the dataset, {len(results) - run['seed_cases']} ours; "
             f"{run['multi_turn']} multi-turn) · turns: {run['turns']}")
    L.append(f"- **Overall: {pct(passed, len(results))} of cases pass every check**")
    L.append("")

    L.append("## Targets")
    L.append("")
    L.append("| Target | Goal | Result | Met |")
    L.append("| --- | --- | --- | --- |")
    pa, inv, mh = m["price_accuracy"], m["invented_price_turns"], m["missing_expired_handling"]
    L.append(f"| Price accuracy (shown price & deposit = pricing function) | 100% | {pct(*pa)} | {'✅' if pa[0] == pa[1] else '❌'} |")
    L.append(f"| Invented prices (money in a reply not from a stored quote or policy) | 0 | {inv} turn(s) | {'✅' if inv == 0 else '❌'} |")
    L.append(f"| Missing / expired rates handled (no price + staff flag) | 100% | {pct(*mh)} | {'✅' if mh[0] == mh[1] else '❌'} |")
    L.append("")

    L.append("## Pass rate per requirement")
    L.append("")
    L.append("Case-level: a case passes only if all of its checks pass (code checks and, where it has a "
             "behaviour expectation, the LLM judge).")
    L.append("")
    L.append("| Requirement | Cases passing |")
    L.append("| --- | --- |")
    by_req: dict[str, list[dict]] = defaultdict(list)
    for r in results:
        for req in r["requirements"]:
            by_req[req].append(r)
    for req in [*REQUIREMENT_NAMES, *sorted(set(by_req) - set(REQUIREMENT_NAMES))]:
        if req in by_req:
            rs = by_req[req]
            L.append(f"| {req} {REQUIREMENT_NAMES.get(req, '')} | {pct(sum(x['passed'] for x in rs), len(rs))} |")
    L.append("")

    L.append("## Code checks (all turns)")
    L.append("")
    L.append("| Check | Passing |")
    L.append("| --- | --- |")
    for key, label in [("ui_valid", "UI payload valid against catalog (R3)"),
                       ("staff_leak_free", "No costs/margins/internal data shown (R5)"),
                       ("unpublished_free", "No unpublished (draft) content used (R4)"),
                       ("enquiries_saved", "Quote saved as private enquiry with cost, GP% and trace id (R7)")]:
        L.append(f"| {label} | {pct(*m[key])} |")
    L.append(f"| Turns that errored | {m['errors']} |")
    L.append(f"| LLM judge (behaviour cases) | {pct(*m['judge'])} |")
    L.append("")

    if calibration:
        L.append("## LLM judge agreement with human labels")
        L.append("")
        L.append(f"**{pct(calibration['agree'], calibration['total'])}** agreement on "
                 f"`evals/labels/judge_calibration.jsonl`.")
        L.append("")
        L.append("| Case | Human | Judge | Agree | Judge's reason |")
        L.append("| --- | --- | --- | --- | --- |")
        for row in calibration["rows"]:
            L.append(f"| {row['id']} | {row['human']} | {row['judge']} | {'✅' if row['agree'] else '❌'} | {row['reason']} |")
        L.append("")

    failures = [r for r in results if not r["passed"]]
    L.append(f"## Failing cases ({len(failures)})")
    L.append("")
    if not failures:
        L.append("None.")
    for r in failures:
        L.append(f"### {r['id']} · {r['category']} · {', '.join(r['requirements'])}")
        L.append("")
        L.append(f"> {' ⟶ '.join(r['turns'])}")
        L.append("")
        for c in r["checks"]:
            if not c["passed"]:
                where = f" (turn {c['turn']})" if c.get("turn") else ""
                L.append(f"- ❌ `{c['name']}`{where}: {c['detail']}")
        for n, t in enumerate(r["transcript"], start=1):
            link = f" — [trace]({t['trace_url']})" if t.get("trace_url") else ""
            L.append(f"- Turn {n} reply{link}: {t['reply'][:300]!r}")
        L.append("")

    L.append("## All cases")
    L.append("")
    L.append("| Case | Source | Category | Requirements | Result | Trace |")
    L.append("| --- | --- | --- | --- | --- | --- |")
    for r in results:
        last = r["transcript"][-1] if r["transcript"] else {}
        link = f"[trace]({last['trace_url']})" if last.get("trace_url") else ""
        L.append(f"| {r['id']} | {r['source']} | {r['category']} | {', '.join(r['requirements'])} | "
                 f"{'✅ pass' if r['passed'] else '❌ fail'} | {link} |")
    L.append("")
    return "\n".join(L)
