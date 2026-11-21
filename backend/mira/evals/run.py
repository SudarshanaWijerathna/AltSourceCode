"""Eval suite entrypoint:  npm run eval  [-- --only S02,P01 --category pricing --no-judge --label before]

Runs every case through the real agent (Gemini + Langfuse), applies code checks and the LLM
judge, calibrates the judge against human labels, scores each case on its Langfuse trace, and
writes evals/reports/<run>/report.md (+ results.json) and evals/reports/latest.md.
"""

from __future__ import annotations

import os

# Isolate eval runs before any mira settings are read.
os.environ.setdefault("MIRA_ENVIRONMENT", "eval")
os.environ.setdefault("MIRA_DB_URL", "sqlite:///./data/eval.db")

import argparse
import json
import subprocess
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from datetime import datetime

from mira.config import REPO_ROOT, get_settings
from mira.evals.cases import Case, load_cases
from mira.evals.checks import Check, outcome_checks, turn_checks
from mira.evals.judge import Judge, Transcript, calibrate
from mira.evals.report import metrics, render
from mira.tracing import get_langfuse, tracing_enabled


def git_sha() -> str:
    try:
        out = subprocess.run(["git", "rev-parse", "--short", "HEAD"], check=False, capture_output=True, text=True, cwd=REPO_ROOT)
        dirty = subprocess.run(["git", "status", "--porcelain"], check=False, capture_output=True, text=True, cwd=REPO_ROOT)
        return out.stdout.strip() + ("+dirty" if dirty.stdout.strip() else "")
    except OSError:
        return "unknown"


def run_case(mira, judge: Judge | None, case: Case, run_id: str) -> dict:
    session = f"eval-{run_id}-{case.id}"
    transcript: list[dict] = []
    started = time.time()
    for message in case.turns:
        r = mira.turn(session, message, tags=["eval", f"case:{case.id}", f"run:{run_id}"])
        row = mira.deps.store.get(r.enquiry_id) if r.enquiry_id else None
        transcript.append({
            "user": message, "reply": r.reply, "ui": r.ui, "quote": r.quote, "enquiry_id": r.enquiry_id,
            "needs_specialist": r.needs_specialist, "route": r.route, "error": r.error,
            "trace_id": r.trace_id, "trace_url": r.trace_url,
            "staff_cost_usd": row["cost_usd"] if row else None,
        })

    checks: list[Check] = turn_checks(case, transcript, mira.deps.store) + outcome_checks(case, transcript)
    verdict = None
    if judge and case.behaviour:
        t = Transcript([{
            "user": x["user"], "mira": x["reply"], "ui": [c["component"] for c in x["ui"]],
            "sources": [s["source_path"] for c in x["ui"] if c["component"] == "source_list" for s in c["sources"]]
            + [c["source_path"] for c in x["ui"] if c["component"] == "tour_card"],
        } for x in transcript])
        try:
            v = judge(case.behaviour, t)
            verdict = {"passed": v.passed, "reason": v.reason}
            checks.append(Check("judge", case.requirements[0], v.passed, v.reason))
        except Exception as exc:  # noqa: BLE001 - a judge outage must not abort the run
            checks.append(Check("judge", case.requirements[0], False, f"judge error: {exc!r}"[:300]))

    passed = all(c.passed for c in checks)
    result = {
        "id": case.id, "source": case.source, "category": case.category, "requirements": case.requirements,
        "turns": case.turns, "expected": case.expected, "note": case.note, "passed": passed,
        "checks": [asdict(c) for c in checks], "judge": verdict, "transcript": transcript,
        "duration_s": round(time.time() - started, 1),
    }
    if tracing_enabled() and transcript and transcript[-1]["trace_id"]:
        failed = [c.name for c in checks if not c.passed]
        try:
            get_langfuse().create_score(
                name="eval-case-pass", value=1 if passed else 0, data_type="BOOLEAN",
                trace_id=transcript[-1]["trace_id"],
                comment=f"{case.id}: " + ("all checks passed" if passed else "failed " + ", ".join(failed)),
                metadata={"run_id": run_id, "case": case.id},
            )
        except Exception as exc:  # noqa: BLE001 - scoring is best effort
            print(f"  (could not score {case.id} in Langfuse: {exc!r})", flush=True)
    mark = "PASS" if passed else "FAIL " + ",".join(c.name for c in checks if not c.passed)
    print(f"  {case.id:4} {mark}  ({result['duration_s']}s)", flush=True)
    return result


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Run the Mira evaluation suite.")
    ap.add_argument("--only", help="comma-separated case ids")
    ap.add_argument("--category", help="only cases in this category")
    ap.add_argument("--workers", type=int, default=4)
    ap.add_argument("--no-judge", action="store_true", help="skip the LLM judge and calibration")
    ap.add_argument("--calibrate-only", action="store_true", help="only measure judge agreement")
    ap.add_argument("--label", default="", help="name for this run, e.g. 'before-fix'")
    args = ap.parse_args(argv)

    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    s = get_settings()
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S")
    judge = None if args.no_judge else Judge()

    calibration = None
    if judge:
        print("Calibrating judge against human labels...", flush=True)
        calibration = calibrate(judge)
        print(f"  agreement {calibration['agree']}/{calibration['total']}", flush=True)
    if args.calibrate_only:
        return 0

    from mira.agent import Mira

    cases = load_cases()
    if args.only:
        wanted = {x.strip() for x in args.only.split(",")}
        cases = [c for c in cases if c.id in wanted]
    if args.category:
        cases = [c for c in cases if c.category == args.category]
    print(f"Running {len(cases)} cases with {args.workers} workers (today={s.mira_today}, env={s.mira_environment})",
          flush=True)

    mira = Mira()
    started = time.time()
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        results = list(pool.map(lambda c: run_case(mira, judge, c, run_id), cases))
    get_langfuse().flush()

    run = {
        "run_id": run_id, "label": args.label, "git": git_sha(), "started": datetime.now().isoformat(timespec="seconds"),
        "duration_s": time.time() - started, "today": s.mira_today.isoformat(), "model": s.mira_model_large,
        "judge_model": s.mira_model_large if judge else "(skipped)", "rates_version": mira.deps.engine.rates.version,
        "seed_cases": sum(1 for c in cases if c.source == "seed"),
        "multi_turn": sum(1 for c in cases if len(c.turns) > 1), "turns": sum(len(c.turns) for c in cases),
    }
    out_dir = REPO_ROOT / "evals" / "reports" / (f"{run_id}-{args.label}" if args.label else run_id)
    out_dir.mkdir(parents=True, exist_ok=True)
    report = render(run, results, calibration)
    (out_dir / "report.md").write_text(report, encoding="utf-8")
    (out_dir / "results.json").write_text(
        json.dumps({"run": run, "metrics": metrics(results), "calibration": calibration, "results": results},
                   indent=1, default=str), encoding="utf-8")
    (REPO_ROOT / "evals" / "reports" / "latest.md").write_text(report, encoding="utf-8")

    m = metrics(results)
    print(f"\nCases passing: {sum(r['passed'] for r in results)}/{len(results)}")
    print(f"Price accuracy: {m['price_accuracy'][0]}/{m['price_accuracy'][1]} · invented-price turns: "
          f"{m['invented_price_turns']} · missing/expired handled: {m['missing_expired_handling'][0]}/"
          f"{m['missing_expired_handling'][1]}")
    print(f"Report: {out_dir / 'report.md'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
