"""Eval suite entrypoint: `npm run eval`.

Loads the seed cases (dataset, unchanged) plus our own cases in evals/cases/,
runs code checks and the LLM judge, writes a report to evals/reports/.
"""

import json

from mira.config import REPO_ROOT, get_settings


def load_cases() -> list[dict]:
    s = get_settings()
    cases = [json.loads(line) for line in s.eval_seed.read_text(encoding="utf-8").splitlines() if line.strip()]
    for path in sorted((REPO_ROOT / "evals" / "cases").glob("*.jsonl")):
        cases += [json.loads(l) for l in path.read_text(encoding="utf-8").splitlines() if l.strip()]
    return cases


def main() -> None:
    cases = load_cases()
    print(f"Loaded {len(cases)} eval cases (today={get_settings().mira_today}). Runner not implemented yet.")


if __name__ == "__main__":
    main()
