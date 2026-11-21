"use client";
// The fixed component catalog Mira can choose from. One accent colour per card (brand rule).
import { useState } from "react";

import { type Props, shortSource, usd } from "@/lib/catalog";
import { useSendMessage } from "@/lib/useSendMessage";

/** Every card uses black text and one colour: the brand teal (headings, buttons, chips, focus).
    The label ("Day 4", "Children's ages") sits above the card, not inside it. */
function Card({ label, children, className }: { label: string; children: React.ReactNode; className?: string }) {
  return (
    <section className={className ? `mira-block ${className.replace("mira-card--", "mira-block--")}` : "mira-block"}
             aria-label={label}>
      <p className="mira-card__label">{label}</p>
      <div className={className ? `mira-card ${className}` : "mira-card"}>{children}</div>
    </section>
  );
}

/* ---- Guided inputs: each collects one missing detail. Its button stays disabled until the detail
   is given; it reads "Get my price" when this answer completes the details, otherwise "Continue".
   After sending, the card locks so the same answer can't be sent twice. ---- */

const nextLabel = (final: boolean) => (final ? "Get my price" : "Continue");

function useAnswer() {
  const { send, busy } = useSendMessage();
  const [sent, setSent] = useState(false);
  const answer = async (text: string) => {
    if (sent) return;
    setSent(true);
    await send(text);
  };
  return { answer, locked: sent || busy, sent };
}

function Stepper({ label, value, min, max, onChange, disabled }: {
  label: string; value: number; min: number; max: number; onChange: (v: number) => void; disabled: boolean;
}) {
  return (
    <div className="mira-stepper">
      <span className="mira-stepper__label">{label}</span>
      <div className="mira-stepper__controls">
        <button type="button" className="mira-stepper__btn" aria-label={`Fewer ${label.toLowerCase()}`}
                disabled={disabled || value <= min} onClick={() => onChange(value - 1)}>−</button>
        <span className="mira-stepper__value" aria-live="polite">{value}</span>
        <button type="button" className="mira-stepper__btn" aria-label={`More ${label.toLowerCase()}`}
                disabled={disabled || value >= max} onClick={() => onChange(value + 1)}>+</button>
      </div>
    </div>
  );
}

// The heading asks the question; the payload's `prompt` is kept for screen readers.
export function TravellerPicker({ prompt, final }: Props<"show_traveller_picker">) {
  const { answer, locked, sent } = useAnswer();
  const [adults, setAdults] = useState(2);
  const [children, setChildren] = useState(0);
  const text = `${adults} adult${adults === 1 ? "" : "s"}` +
    (children ? ` and ${children} child${children === 1 ? "" : "ren"} (under 12)` : "");
  // Children still need their ages, so the details are not complete yet.
  const completes = final && children === 0;
  return (
    <Card label="Who's travelling">
      <div className="mira-form" role="group" aria-label={prompt}>
        <Stepper label="Adults" value={adults} min={1} max={20} onChange={setAdults} disabled={locked} />
        <Stepper label="Children (2–11)" value={children} min={0} max={10} onChange={setChildren} disabled={locked} />
        <button className="mira-button" disabled={locked || adults < 1} onClick={() => answer(text)}>
          {sent ? "Sent" : nextLabel(completes)}
        </button>
      </div>
    </Card>
  );
}

const longDate = (iso: string) =>
  new Date(`${iso}T00:00:00`).toLocaleDateString("en-GB", { day: "numeric", month: "long", year: "numeric" });

export function DatePicker({ prompt, min_date, max_date, final }: Props<"show_date_picker">) {
  const { answer, locked, sent } = useAnswer();
  const [date, setDate] = useState("");
  const valid = Boolean(date) && date >= min_date && date <= max_date;
  return (
    <Card label="Start date">
      <div className="mira-form">
        <label>{prompt}
          <input type="date" value={date} min={min_date} max={max_date} disabled={locked}
                 onChange={(e) => setDate(e.target.value)} />
        </label>
        <p className="mira-source">We have rates for {longDate(min_date)} to {longDate(max_date)}.</p>
        <button className="mira-button" disabled={locked || !valid} onClick={() => answer(`Start date: ${longDate(date)}`)}>
          {sent ? "Sent" : nextLabel(final)}
        </button>
      </div>
    </Card>
  );
}

const AGE_OPTIONS = [
  { value: "1", label: "Under 2" },
  ...Array.from({ length: 16 }, (_, i) => ({ value: String(i + 2), label: String(i + 2) })),
];

export function ChildAgesPicker({ count, final }: Props<"show_child_ages_picker">) {
  const { answer, locked, sent } = useAnswer();
  const [ages, setAges] = useState<string[]>(Array(count).fill(""));
  const complete = ages.every(Boolean);
  const text = `Children's ages: ${ages.map((a) => (a === "1" ? "under 2" : a)).join(", ")}`;
  return (
    <Card label="Children's ages">
      <div className="mira-form">
        <div className="mira-ages">
          {ages.map((a, i) => (
            <label key={i}>Child {i + 1}
              <select value={a} disabled={locked}
                      onChange={(e) => setAges((prev) => prev.map((v, j) => (j === i ? e.target.value : v)))}>
                <option value="" disabled>Age</option>
                {AGE_OPTIONS.map((o) => <option key={o.value} value={o.value}>{o.label}</option>)}
              </select>
            </label>
          ))}
        </div>
        <p className="mira-source">Infants under 2 travel free; 12 and over pay adult rates.</p>
        <button className="mira-button" disabled={locked || !complete} onClick={() => answer(text)}>
          {sent ? "Sent" : nextLabel(final)}
        </button>
      </div>
    </Card>
  );
}

export function TourCard({ title, duration, summary, source_path, action }: Props<"show_tour_card">) {
  const { answer, locked, sent } = useAnswer();
  return (
    <Card label={duration}>
      <h3 className="mira-card__title">{title}</h3>
      <p className="mira-card__body">{summary}</p>
      <div className="mira-card__footer">
        <span className="mira-source" title={shortSource(source_path)}>Source: our tour page</span>
        {action === "choose" && (
          <button className="mira-button mira-button--ghost" disabled={locked} onClick={() => answer(`I'd like the ${title}.`)}>
            {sent ? "Chosen" : "Choose this tour"}
          </button>
        )}
      </div>
    </Card>
  );
}

export function ItineraryDay({ day, title, description }: Props<"show_itinerary_day">) {
  const [first, ...rest] = description.split(" · ");
  return (
    <Card label={`Day ${day}`}>
      <h3 className="mira-card__title">{title}</h3>
      <p className="mira-card__body">{first}</p>
      {rest.length > 0 && (
        <ul className="mira-list">
          {rest.map((item) => <li key={item}>{item}</li>)}
        </ul>
      )}
    </Card>
  );
}

export function PriceBreakdown({ quote_id, price_usd, deposit_usd, balance_usd, balance_due }: Props<"show_price_breakdown">) {
  const inFull = deposit_usd === price_usd;
  return (
    <Card label="Your price">
      <p className="mira-price">{usd(price_usd)}</p>
      <dl className="mira-rows">
        <div><dt>{inFull ? "Pay when you book" : "Deposit to book"}</dt><dd>{usd(deposit_usd)}</dd></div>
        {!inFull && <div><dt>Balance{balance_due ? ` due by ${balance_due}` : ""}</dt><dd>{usd(balance_usd)}</dd></div>}
      </dl>
      <p className="mira-source">Total for your group, from our 2026/27 rates. Quote {quote_id}.</p>
    </Card>
  );
}

export type BookingOutcome = {
  status: string; message: string; next_step: string; booking_ref?: string | null; deposit_usd?: string | null;
};

/** `preview` shows a finished booking outcome without submitting (used by the /cards gallery). */
export function BookingForm({ quote_id, preview }: Props<"show_booking_form"> & { preview?: BookingOutcome }) {
  const [state, setState] = useState<"idle" | "sending" | "done">(preview ? "done" : "idle");
  const [outcome, setOutcome] = useState<BookingOutcome | null>(preview ?? null);

  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    const form = new FormData(e.currentTarget);
    setState("sending");
    try {
      const res = await fetch("/backend/booking", {
        method: "POST",
        headers: { "content-type": "application/json" },
        body: JSON.stringify({
          quote_id,
          name: form.get("name"),
          email: form.get("email"),
          phone: form.get("phone") || null,
          simulate: form.get("simulate"),
        }),
      });
      setOutcome(res.ok ? await res.json() : {
        status: "booking_failed",
        message: "I couldn't reach our booking system just now, so nothing has been charged.",
        next_step: "Please check the details and try again, or leave your email and our team will follow up.",
      });
    } catch {
      setOutcome({
        status: "booking_failed",
        message: "Your connection dropped before the booking went through. Nothing has been charged.",
        next_step: "Try again in a moment. Your quote is saved.",
      });
    }
    setState("done");
  }

  if (state === "done" && outcome) {
    return <BookingResult outcome={outcome} onRetry={() => setState("idle")} />;
  }

  return (
    <Card label="Reserve this trip">
      <form className="mira-form" onSubmit={submit}>
        <label>Full name<input name="name" required autoComplete="name" /></label>
        <label>Email<input name="email" type="email" required autoComplete="email" /></label>
        <label>Phone (optional)<input name="phone" type="tel" autoComplete="tel" /></label>
        <label>Test mode
          <select name="simulate" defaultValue="success">
            <option value="success">Payment succeeds</option>
            <option value="payment_declined">Card is declined</option>
            <option value="booking_unavailable">Booking system is down</option>
          </select>
        </label>
        <button className="mira-button" disabled={state === "sending"}>
          {state === "sending" ? "Booking…" : "Pay deposit and book"}
        </button>
        <p className="mira-source">Payment is mocked. No card details are collected.</p>
      </form>
    </Card>
  );
}

const RESULT_TITLE: Record<string, string> = {
  confirmed: "You're booked",
  payment_failed: "Payment didn't go through",
  booking_failed: "Booking not completed",
  not_bookable: "We can't book this yet",
};

function ResultIcon({ ok }: { ok: boolean }) {
  return (
    <span className="mira-result__icon" aria-hidden>
      <svg viewBox="0 0 24 24" width="28" height="28" fill="none" stroke="currentColor" strokeWidth="2.6" strokeLinecap="round" strokeLinejoin="round">
        {ok ? <path d="M5 12.5l4.5 4.5L19 7.5" /> : <path d="M7 7l10 10M17 7L7 17" />}
      </svg>
    </span>
  );
}

/** Small icon button that copies `text`; shows a tick for a moment after copying. */
function CopyButton({ text, label }: { text: string; label: string }) {
  const [copied, setCopied] = useState(false);
  async function copy() {
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      // Clipboard API blocked (e.g. insecure context): fall back to a temporary selection.
      const area = document.createElement("textarea");
      area.value = text;
      document.body.appendChild(area);
      area.select();
      document.execCommand("copy");
      area.remove();
    }
    setCopied(true);
    setTimeout(() => setCopied(false), 1500);
  }
  return (
    <button type="button" className="mira-copy" onClick={copy} aria-label={copied ? "Copied" : label} title={copied ? "Copied" : label}>
      <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" aria-hidden>
        {copied ? <path d="M5 12.5l4.5 4.5L19 7.5" /> : (<><rect x="9" y="9" width="11" height="11" rx="2" /><path d="M5 15V6a2 2 0 0 1 2-2h9" /></>)}
      </svg>
    </button>
  );
}

/** Outcome of "Pay deposit and book": centred icon, title, details and the next step. */
function BookingResult({ outcome, onRetry }: { outcome: BookingOutcome; onRetry: () => void }) {
  const ok = outcome.status === "confirmed";
  return (
    <section className={`mira-card mira-result ${ok ? "mira-result--ok" : "mira-result--fail"}`} role="status">
      <ResultIcon ok={ok} />
      <h3 className="mira-result__title">{RESULT_TITLE[outcome.status] ?? (ok ? "You're booked" : "Not booked yet")}</h3>
      <p className="mira-result__text">{outcome.message}</p>
      {ok && outcome.booking_ref && (
        <p className="mira-result__ref" aria-label={`Booking reference ${outcome.booking_ref}`}>
          <strong>{outcome.booking_ref}</strong>
          <CopyButton text={outcome.booking_ref} label="Copy booking reference" />
        </p>
      )}
      <p className="mira-result__text mira-result__text--muted">{outcome.next_step}</p>
      {!ok && <button className="mira-button mira-result__action" onClick={onRetry}>Try again</button>}
    </section>
  );
}

export function SpecialistHandoff({ message }: Props<"show_specialist_handoff">) {
  return (
    <Card label="Passed to our team">
      <p className="mira-card__body">{message}</p>
      <p className="mira-source">A travel specialist has been notified and will confirm with you.</p>
    </Card>
  );
}

export function SourceList({ sources }: Props<"show_source_list">) {
  return (
    <Card label="Sources" className="mira-card--sources">
      <ul className="mira-list">
        {sources.map((s) => (
          <li key={s.source_path} title={shortSource(s.source_path)}>{s.title}</li>
        ))}
      </ul>
    </Card>
  );
}
