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
| `npm run chat` | Chat with Mira in the terminal (shows UI components and trace links) |
| `npm run eval` | Run the evaluation suite → `evals/reports/` |

"Today" is configurable with `MIRA_TODAY` (default `2026-11-19`, which the seed evals assume).

## Architecture

```
Browser (Next.js + CopilotKit)          npm run chat (terminal)
   │  POST /chat  (AG-UI bridge next)        │
   ▼                                          ▼
FastAPI ──► Mira.turn()  — one Langfuse trace per turn, session = conversation
              │
              ▼  LangGraph (typed MiraState, checkpointed per session)
            router  (LLM: structured TurnAnalysis → code merges profile, code picks route)
              ├─► discovery  (code: next missing detail, ≤3 questions, tour suggestions)
              ├─► pricing    (code: PricingEngine → private enquiry + trace id)
              ├─► answer     (BM25 retrieval → LLM answers from numbered passages → code checks citations)
              ├─► handoff    (code: unknown tour → enquiry for sales)
              └─► respond    (LLM writes words only → price guard → name scrub
                              → price sentence from stored quote → UI catalog validation)
   │
   ├── SQLite: enquiries (cost / price / GP% / staff reason / trace id)
   └── Langfuse: agent → chains → generations (classify-turn, write-reply),
                 retriever (retrieve-content), tool (calculate-quote),
                 guardrails (check-grounding, check-price-mentions, validate-ui-components);
                 personal details masked at export
```

Only `router` and `respond` call the LLM. Prices, routing decisions, permissions and UI validation
are code. The responder LLM never receives a price, cost or staff reason, and any money amount it
writes anyway is caught by the price guard and replaced.

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

## Pricing

`mira.pricing.engine.PricingEngine.quote()` implements the workbook's READ ME rules with exact
fractions (no float rounding), returns a `StaffQuote` (cost lines, cost, margin, GP%, rates version)
and exposes only `traveller_view()` (price, deposit, balance) to the traveller and the LLM.
Anything it cannot price returns a status and a staff-only reason — never a number:

| Status | When |
| --- | --- |
| `missing_rates` | A rate the price needs is not in the workbook (e.g. no single room at H04, no rates for T10/T16) |
| `expired_rates` | Rates don't cover the travel dates (H07 ended Oct 2026; anything after 31 Oct 2027) |
| `ambiguous_rates` | Two rate rows with different prices cover the same night (H03, Jan–Mar 2027) |
| `not_available` | Draft page, ended offer, or tour page and rate sheet disagree on duration |
| `refer_to_sales` | More than 20 travellers |
| `invalid_request` | Start date in the past (not a staff flag — Mira asks for another date) |

Margins come from the workbook; `MIRA_MARGIN_DAY_TOUR` / `MIRA_MARGIN_MULTI_DAY` override them
without touching the workbook.

## Answering from content

`mira/retrieval` indexes **published** pages only (the draft T15 never reaches Mira), split at
headings, with an overview chunk per tour from its front matter. Retrieval is BM25: the corpus is
~4k words of proper nouns and policy terms, so lexical search is precise, deterministic, explainable
in the trace and needs no embedding service.

- **Prices never come from content.** Teaser prices ("From USD 85") and offers ("save 15%") are
  stripped from tour and destination chunks. Policy fees (the USD 50 admin fee) are policy facts and
  may be quoted only when the cited passage contains them; the price guard enforces this.
- **Newer policies win** (`retrieval/rules.py`). P02 and P03 state that they replace older terms on
  tour pages, so Galle Fort's "24 hours" cancellation line and Kandy Heritage Stay's "kids under 12
  stay free!" are removed before the LLM sees them, and the replacing policy is retrieved instead.
- **Answers must cite.** The answer LLM returns `answered`, `answer`, `citations`. Code accepts the
  answer only if it cites passages that were actually retrieved; otherwise Mira says it doesn't have
  that information and offers to ask the team. Sources are appended to the reply and sent as a
  `source_list` component.

## Dataset notes

Data issues the loader handles (all reported in `RateBook.warnings`):

- Hotels `F8`/`F10`: H02 double rate stored as text `'LKR 28,000'` → parsed.
- Hotels `D33`: H08 Peak start date stored as text `'15/12/2026'` → parsed as day/month/year.
- H10 Cinnamon Wild Yala is contracted in **USD** (Notes column) → converted to LKR at the FX rate, not divided by it.
- Tour id `T-13` → normalised to `T13` to match its tour page.
- H04 has no single-room rate → solo travellers on T12 get a specialist hand-over (seed S04).
- H07 rates end 31 Oct 2026 → T11 is flagged as expired (seed S05).
- H03 has two overlapping Peak rows for Jan–Mar 2027 (25,000 vs 34,000, "Revised per supplier email?")
  → **decision:** flag as ambiguous rather than pick one.
- **Decision:** T06's page says "1 night / 2 days" but the rate sheet prices a 0-night day tour → not quoted.
- **Decision:** T14 "Winter 2023/24 Early Bird" is an ended offer → not quoted (`pricing/rules.py`).
- T15 is a draft marked "not launched yet" → never quoted.
- Sample quote **Q-1043 is wrong**: it omits the children's extra beds (READ ME rule 4). Correct hotels
  are LKR 210,000 and the price USD 2,965, which matches eval seed S03. Tests assert the corrected figure.
- The dataset README says 15 seed eval cases; `eval_seed.jsonl` contains 17 (matching the brief).

## Known limitations

_To be filled in as the build progresses._

## AI tools used

Claude Code (Anthropic) was used to help scaffold this repository.
