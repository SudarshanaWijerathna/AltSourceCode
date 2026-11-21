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
| `npm run eval` | Run the evaluation suite → `evals/reports/latest.md` (options: `-- --only S02,P01`, `--category pricing`, `--no-judge`, `--label before`) |

"Today" is configurable with `MIRA_TODAY` (default `2026-11-19`, which the seed evals assume).

## Architecture

```
Browser: Next.js + CopilotKit v2 (CopilotChat + useRenderTool per catalog component)
   │  /api/copilotkit  (Copilot Runtime, TypeScript, open-source mode)
   │  └─ HttpAgent ──► POST /agent   AG-UI SSE: text message + one tool call per component
   │                                 ("show_tour_card", ...), validated against the catalog
   ▼                                                         npm run chat (terminal) ─┐
FastAPI ──► Mira.turn()  — one Langfuse trace per turn, session = conversation ◄───────┘
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

## Generative UI

Mira's backend chooses components from a fixed catalog (`backend/mira/ui/catalog.py`):
`traveller_picker`, `tour_card`, `itinerary_day`, `price_breakdown`, `booking_form`,
`specialist_handoff`, `source_list`. The graph builds them from code (a price card only from a
stored quote; itinerary days only from the tour page) and validates them twice before the browser:
in the `respond` node and again in the AG-UI endpoint (`mira/agui.py`) just before encoding.

Over AG-UI each component is a **backend tool call** `show_<component>` whose arguments are the
payload. The frontend renders them with CopilotKit's `useRenderTool` (tool-call rendering,
`frontend/components/MiraRenderers.tsx`) after a third check against Zod mirrors of the catalog
(`frontend/lib/catalog.ts`); a wildcard renderer draws nothing for anything else. No component
executes code in the browser except the traveller picker / "Price this tour" buttons (they send a
message as the traveller) and the booking form.

- **Brand:** `frontend/scripts/brand-css.mjs` generates CSS variables from
  `brand/brand_pack.json` before every dev/build; one accent colour per card, cards ≤ 320 px,
  Inter, transitions < 200 ms, no scroll animation.
- **Mobile and desktop:** checked in headless Edge at 1280×900 and 390×844 (no horizontal overflow).
- **Mock booking/payment:** `POST /booking` charges the stored quote's deposit (the browser never
  sends a price). "Test mode" lets the demo pick *card declined* or *booking system down*; both give
  a friendly message and a way forward, never an error page. Contact details are stored only with
  the private enquiry and never traced.
- The CopilotKit AG-UI inspector is off unless `NEXT_PUBLIC_COPILOTKIT_INSPECTOR=true`; CopilotKit
  runtime telemetry is off unless `COPILOTKIT_TELEMETRY_DISABLED=false`.

## Staff, returning visitors and content approval

Staff sign in on **`/staff`** with a staff key (`MIRA_STAFF_USERS`, format `name:role:key`; the
defaults `demo-staff-key` / `demo-approver-key` are for local demos only). Roles are enforced in
code by `mira/auth` (FastAPI dependencies: 401 without a key, 403 without the permission):

| Permission | staff | approver |
| --- | --- | --- |
| View and edit enquiries (notes, follow-up status) | ✓ | ✓ |
| Create AI-written drafts | ✓ | ✓ |
| Publish or reject drafts | ✗ | ✓ |

- **Private enquiries (Req 7).** Every quote attempt, flag, custom request and booking is an
  enquiry with price, deposit, cost, GP%, cost lines, staff-only reason, contact details (if
  booked), follow-up status, notes and a link to the Langfuse trace that produced it.
- **Returning visitors (Req 2).** The browser keeps a random visitor id (no personal data) and sends
  it in the AG-UI thread id (`v-<visitor>.<session>`). Mira remembers trip facts only (tour, dates,
  travellers), never names or contact details. A returning visitor sees a *Welcome back* card with
  the last quote **re-priced today**: it is shown only if the price is unchanged, otherwise Mira
  offers to re-check. A new session starts from the remembered trip, so Mira doesn't ask again
  ("Can you add our son? He is 8." is quoted straight away). *Forget me* drops the id.
- **AI-written content (Req 8).** A staff command such as *"Add a 5-day Hill Country tour using the
  Ella photos"* runs the content agent (`mira/content_admin`): it retrieves published pages, the LLM
  drafts a tour as structured data, and code removes prices, unknown destinations and hotels not in
  our pages, and notes gaps for the approver (the dataset has no photos, so it says so instead of
  inventing any). The draft is stored in the database only. Mira can't see it. When an Approver
  publishes it, a normal page is written to `data/published_content/` (never into the dataset) and
  Mira's catalog and search index are refreshed, so Mira can answer about it immediately. A new tour
  has no rates, so price requests go to a specialist.

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

## Evaluation

`npm run eval` runs every case through the real agent (Gemini + Langfuse), then writes
`evals/reports/<run>/report.md` and `results.json`, and copies the report to `evals/reports/latest.md`.
Committed snapshots are in [`evals/snapshots/`](evals/snapshots/); problems found and fixed are in
[`evals/findings.md`](evals/findings.md).

- **Cases:** 61 = the dataset's 17 seed cases (read in place, unchanged) + 44 of ours
  (`evals/cases/build_cases.py` → `mira_cases.jsonl`), 13 multi-turn or multi-session, covering
  R1–R8, prompt injection and off-topic requests. R2 cases run two sessions for the same visitor;
  R8 cases run against fixtures (`evals/fixtures/content.json`): one page published through the
  real publish path into a fresh directory, one left as an unapproved draft whose words must never
  appear in a reply.
- **Code checks** wherever there is an exact answer, on every turn: price and deposit equal the
  pricing function; no money amount in a reply that isn't the stored quote or a policy fee; every UI
  payload validates against the catalog and matches the stored quote; no costs, margins or internal
  rate data shown; no words that exist only on unpublished pages; cited sources are published pages;
  every quote saved as a private enquiry with cost, GP% and its trace id.
- **LLM judge** (Gemini) for behaviour expectations. It sees the conversation, the components shown
  and the text of the cited pages. Agreement with human labels on 10 calibration cases
  (`evals/labels/judge_calibration.jsonl`, 5 real replies + 5 deliberately flawed) is in every report.
- **Tracing:** each case runs in its own Langfuse session `eval-<run>-<case>` in the `eval`
  environment, tagged `case:<id>`; the case verdict is attached as an `eval-case-pass` score, and the
  report links the trace of every failing turn.

Latest result (2026-11-21, `gemini-3.8-flash`, [`evals/snapshots/2026-11-21-extended-final.md`](evals/snapshots/2026-11-21-extended-final.md)):
**61/61 cases**, price accuracy 25/25, 0 invented prices, missing/expired handling 14/14, judge
agreement 10/10. One earlier run during a Gemini outage scored 47/61 (all failures were dropped
connections; still 0 invented prices, see `evals/findings.md`).

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
