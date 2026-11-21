# Mira — AI Travel Booking Assistant

Conversational booking assistant for **Ceylon Compass Holidays** (fictional). Mira discovers the
trip, answers from tour content with sources, quotes prices computed by deterministic code from the
rate workbook, renders its own UI from a fixed component catalog, and saves every quote as a private
enquiry for staff.

> Status: **project scaffold** — structure, contracts and tooling are in place; features are being built.

## Quick start

Requirements: Python 3.11+, Node 20+.

```bash
cp .env.example .env        # add your Gemini and Langfuse keys
npm start                   # one command: installs everything, starts API (:8000) + web (:3000)
```

| Command | What it does |
| --- | --- |
| `npm start` | Setup + run the whole system |
| `npm run dev` | Run API and web (after setup) |
| `npm test` | Backend unit tests (incl. pricing) |
| `npm run eval` | Run the evaluation suite → `evals/reports/` |

"Today" is configurable with `MIRA_TODAY` (default `2026-11-19`, which the seed evals assume).

## Architecture (planned)

```
Browser (Next.js + CopilotKit)
   │  AG-UI events (text + validated UI component payloads)
   ▼
FastAPI ── LangGraph (typed MiraState)
             router ──► discovery     (≤3 questions)
                    ├─► answer        (retrieval over published content, citations)
                    └─► pricing       (deterministic code → rates DB; no LLM arithmetic)
                          ▼
                     ui_composer      (picks catalog components, validates with Pydantic)
   │
   ├── SQLite: enquiries (cost / price / GP% / trace id), visitors, drafts, approvals
   └── Langfuse: one trace per traveller turn, PII redacted
```

## Repository layout

```
backend/mira/
  config.py            settings, configurable "today", dataset paths
  state.py             typed shared graph state
  graph/               LangGraph builder + nodes
  pricing/             pricing engine + quote models (staff vs traveller views)
  data/                loaders for content Markdown and the rate workbook (read-only)
  ui/catalog.py        generative-UI component catalog + validation
  enquiries/           private enquiry storage
  content_admin/       AI drafts → Approver-only publishing
  auth/                deterministic role checks
  tracing.py           Langfuse integration
  evals/run.py         eval runner
backend/tests/         unit tests (pricing, catalog, smoke)
frontend/              Next.js app: traveller chat (/) and staff page (/staff)
evals/cases/           our own eval cases (seed cases are read from the dataset)
evals/labels/          human labels for LLM-judge agreement
evals/reports/         generated reports (git-ignored)
docs/ceylon-compass-dataset/   provided dataset — kept unchanged
scripts/               cross-platform setup/launch helpers
```

## Design decisions

- **Prices are never produced by the model.** The pricing node calls `mira.pricing.engine.quote()`;
  UI price components reference a stored `quote_id`. Missing/expired rates return a status, not a guess.
- **Two quote views.** `StaffQuote` (cost, margin, GP%) is stored; only `TravellerQuote` fields reach
  the traveller or the LLM.
- **Catalog validation on both ends.** Pydantic on the server, Zod on the client.
- **Dataset is read-only.** All cleaning happens in loaders; the files in `docs/` are not edited.

## Dataset notes

- The dataset README says 15 seed eval cases; `eval_seed.jsonl` contains 17 (matching the brief).

## Known limitations

_To be filled in as the build progresses._

## AI tools used

Claude Code (Anthropic) was used to help scaffold this repository.
