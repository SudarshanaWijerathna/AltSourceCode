# Problems found through traces and evals

Candidates for the "one real problem" section of the evaluation report. Each entry links the
evidence (Langfuse trace), the root cause, the fix and the before/after result.

## F1 · Grounded answers refused partial information (S17, S09)

**Found:** 21 Nov 2026, live smoke run of the grounding seeds after adding retrieval.

**Symptom:** "Tell me about Polonnaruwa." (seed S17) and "Is Little Adam's Peak on any of your
tours?" both returned *"I do not have that information in our tour pages"*, although retrieval
returned the right passages (T09/T08/T16 itinerary days for Polonnaruwa; the Ella destination page).

**Evidence:** trace `df09ce5caa98fabba1fb4d4c728506af` → `retrieve-content` returned 6 relevant
passages; `answer-from-content` thinking: *"There's nothing in here that actually describes
Polonnaruwa … if the passages don't clearly answer the question, I need to say `answered: false`"*;
`check-grounding` → `grounded: false`.

**Root cause:** the answer prompt said *"If the passages do not clearly answer the question, set
answered=false"*. The model read "Tell me about X" as needing a full description, so partial but
correct content was discarded. S17 expects exactly that partial answer ("answers only from what the
tour pages say about Polonnaruwa").

**Fix:** prompt now asks for what the passages say, even if partial, followed by what our pages
don't cover and an offer to ask the team; still no general knowledge; explicit note that
"Little Adam's Peak" is not "Adam's Peak" (`mira/graph/prompts.py`, `ANSWER_SYSTEM`).

| Case | Before | After |
| --- | --- | --- |
| S17 Polonnaruwa | "I do not have that information" | Names the 3 itineraries that stop there and what's included; says history isn't covered; cites 3 tour pages |
| S09 Yala in September | "I do not have that information" | Says safaris run at dawn/late afternoon and which tours visit; says September opening isn't stated; offers to check |
| X3 Little Adam's Peak | "I do not have that information" | Ella page mentions it; Ella tours named; not confirmed as an included stop; offers to check |
| S07, S08, X1, X2, S06, S10 | correct | unchanged |

To be re-measured by the eval suite once it exists (the grounding pass rate before/after).
