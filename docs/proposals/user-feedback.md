# Proposal: traveller feedback on Mira's replies (not implemented)

**Status:** proposed, not built. Estimated effort for the recommended set: about half a day.
**Why it is not built yet:** it is not required by the brief, and the brief values a solid core with
honest evaluation over extra features. This document records the design so it can be added later.

## Why

The conversation is the product, so the traveller's reaction to each reply is the most direct
quality signal we can get from real use. Captured as Langfuse scores on the trace that produced the
reply, it complements the offline evaluation suite (`npm run eval`): the suite measures what we
expect; feedback surfaces what we did not anticipate. Each score points at a trace that can be
opened, read, added to the eval dataset and fixed.

## Proposed signals

Following Langfuse's guidance on capturing user signals (explicit ratings, behavioural, conversation
and outcome signals). Score names describe the observed signal, not the quality we hope it means.

| Priority | Signal (score name) | Type | What it indicates, limits and biases | Effort | Implementation |
| --- | --- | --- | --- | --- | --- |
| P0 | `response_rating` | boolean (👍 = 1, 👎 = 0) | Explicit judgement of one reply. Rare, and skewed towards people with strong reactions: use it to find traces worth reading, not as a quality metric. | S | CopilotKit thumbs → `POST /feedback` → `create_score` |
| P0 | `thumbs_down_reason` | categorical: `wrong_price`, `wrong_information`, `did_not_answer`, `other` (+ optional comment) | Explains a 👎 and makes failures easy to group. The comment is free text and may contain personal details, so it is masked before it reaches Langfuse. | S | reason picker shown after 👎; second score, comment attached |
| P1 | `price_reported` | boolean | A `wrong_price` report also flags the enquiry for staff (follow-up status), tying feedback to the non-negotiable "never show a wrong price" rule. | XS | same endpoint; updates the private enquiry |
| P2 | `response_copied` | boolean | Behavioural signal of a useful text answer, captured without asking. Weak on its own. | XS | copy-button click → score |
| deferred | conversation signals (rephrasing, "talk to a human", corrections) | categorical | Much higher coverage than ratings, but read from free text. | M | Langfuse evaluator over production traces |

**Recommended first step:** P0 + P1.

## Design

```
Browser (CopilotChat)                         Backend (FastAPI)                     Langfuse
  👍 / 👎 on a reply  ── onThumbsUp/Down ──►  POST /feedback                      
  (reason picker on 👎)                         {message_id, rating, reason?,        
                                                 comment?}                          
                                                 ├─ trace_id from message_id         
                                                 ├─ redact(comment)  ────────────►  score on that trace
                                                 └─ wrong_price → flag enquiry       (response_rating,
                                                                                      thumbs_down_reason)
```

1. **Link each reply to its trace.** The AG-UI endpoint (`backend/mira/agui.py`) already has the
   turn's `trace_id`. Use it in the assistant message id it emits (`msg_<trace_id>`), so a rating
   on a message identifies the trace without any extra lookup or client-side state.
2. **Frontend.** CopilotKit v2's assistant message already provides thumbs-up/down buttons through
   `onThumbsUp` / `onThumbsDown` (slots `thumbsUpButton` / `thumbsDownButton`). Pass handlers from
   `CopilotChat`; on 👎 show a small reason picker (four options + optional comment) styled like the
   other catalog cards. Disable the buttons after one rating per message.
3. **Backend.** `POST /feedback` validates the message id (32-hex trace id), the rating and the reason
   (enum), masks the comment with `mira.tracing.redact`, and calls
   `get_langfuse().create_score(name="response_rating", value=0|1, data_type="BOOLEAN", trace_id=…)`
   plus, for 👎, `create_score(name="thumbs_down_reason", value=<reason>, data_type="CATEGORICAL",
   comment=<masked>)`. A `wrong_price` reason also sets the related enquiry's follow-up status so it
   appears on the staff page. No personal details are stored with the score.
4. **Score configs.** Create the two score configs in Langfuse so values are validated and appear
   consistently in filters, dashboards and score analytics.

## Using the feedback

- Filter traces by `response_rating = 0` for a concrete list to investigate; group by
  `thumbs_down_reason`.
- Turn confirmed failures into cases in `evals/cases/build_cases.py`, fix, and re-run the suite
  (the same loop documented in `evals/findings.md`).
- Add a section to the eval report with rating counts per route (quote, answer, hand-off) once
  there is enough traffic to be meaningful.

## Tests to add when implemented

- `POST /feedback` scores the right trace with the right name, value and data type (Langfuse client
  mocked); rejects malformed message ids and unknown reasons.
- Comments are masked (emails, phone numbers, names) before scoring.
- A `wrong_price` report flags the enquiry; other reasons do not.
- Frontend: one rating per message; the reason picker only appears on 👎.

## Related change already made

CopilotKit's per-reply **Copy** button copies only the reply text, not the cards. It is now hidden
on replies that show cards and kept on text answers (whose only card is the Sources list), where the
text is the whole answer (`frontend/app/globals.css`).
