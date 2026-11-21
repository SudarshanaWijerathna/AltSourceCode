"use client";
// The fixed component catalog Mira can choose from. One accent colour per card (brand rule).
import { useState } from "react";

import { type Props, shortSource, usd } from "@/lib/catalog";
import { useSendMessage } from "@/lib/useSendMessage";

/** Every card uses black text and one colour: the brand teal (headings, buttons, chips, focus). */
function Card({ label, children, className }: { label: string; children: React.ReactNode; className?: string }) {
  return (
    <section className={className ? `mira-card ${className}` : "mira-card"}>
      <p className="mira-card__label">{label}</p>
      {children}
    </section>
  );
}

const TRAVELLER_TEXT: Record<string, string> = {
  solo: "Just me, travelling solo.",
  couple: "We're a couple, two adults.",
  family: "We're a family with children.",
  group: "We're a group of friends.",
};

// The heading already asks the question (and Mira's reply above usually does too), so the payload's
// `prompt` is not repeated in the card; it is kept for screen readers via aria-label.
export function TravellerPicker({ prompt, options }: Props<"show_traveller_picker">) {
  const { send, busy } = useSendMessage();
  return (
    <Card label="Who's travelling">
      <div className="mira-chips" role="group" aria-label={prompt}>
        {options.map((o) => (
          <button key={o} className="mira-chip" disabled={busy} onClick={() => send(TRAVELLER_TEXT[o])}>
            {o[0].toUpperCase() + o.slice(1)}
          </button>
        ))}
      </div>
    </Card>
  );
}

export function TourCard({ title, duration, summary, source_path, priced }: Props<"show_tour_card">) {
  const { send, busy } = useSendMessage();
  return (
    <Card label={duration}>
      <h3 className="mira-card__title">{title}</h3>
      <p className="mira-card__body">{summary}</p>
      <div className="mira-card__footer">
        <span className="mira-source" title={shortSource(source_path)}>Source: our tour page</span>
        {!priced && (
          <button className="mira-button mira-button--ghost" disabled={busy} onClick={() => send(`I'd like a price for the ${title}.`)}>
            Price this tour
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
