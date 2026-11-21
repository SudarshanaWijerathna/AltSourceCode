"use client";
// The fixed component catalog Mira can choose from. One accent colour per card (brand rule).
import { useState } from "react";

import { type Props, shortSource, usd } from "@/lib/catalog";
import { useSendMessage } from "@/lib/useSendMessage";

type Accent = "teal" | "leaf" | "sun" | "sky" | "coral" | "orange";

function Card({ accent, label, children }: { accent: Accent; label: string; children: React.ReactNode }) {
  return (
    <section className="mira-card" style={{ ["--accent" as string]: `var(--${accent === "orange" ? "brand-orange" : `accent-${accent}`})` }}>
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

export function TravellerPicker({ prompt, options }: Props<"show_traveller_picker">) {
  const { send, busy } = useSendMessage();
  return (
    <Card accent="coral" label="Who's travelling">
      <p className="mira-card__body">{prompt}</p>
      <div className="mira-chips">
        {options.map((o) => (
          <button key={o} className="mira-chip" disabled={busy} onClick={() => send(TRAVELLER_TEXT[o])}>
            {o[0].toUpperCase() + o.slice(1)}
          </button>
        ))}
      </div>
    </Card>
  );
}

export function TourCard({ title, duration, summary, source_path }: Props<"show_tour_card">) {
  const { send, busy } = useSendMessage();
  return (
    <Card accent="teal" label={duration}>
      <h3 className="mira-card__title">{title}</h3>
      <p className="mira-card__body">{summary}</p>
      <div className="mira-card__footer">
        <span className="mira-source">Source: {shortSource(source_path)}</span>
        <button className="mira-button mira-button--ghost" disabled={busy} onClick={() => send(`I'd like a price for the ${title}.`)}>
          Price this tour
        </button>
      </div>
    </Card>
  );
}

export function ItineraryDay({ day, title, description }: Props<"show_itinerary_day">) {
  const [first, ...rest] = description.split(" · ");
  return (
    <Card accent="sky" label={`Day ${day}`}>
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
    <Card accent="orange" label="Your price">
      <p className="mira-price">{usd(price_usd)}</p>
      <dl className="mira-rows">
        <div><dt>{inFull ? "Pay when you book" : "Deposit to book"}</dt><dd>{usd(deposit_usd)}</dd></div>
        {!inFull && <div><dt>Balance{balance_due ? ` due by ${balance_due}` : ""}</dt><dd>{usd(balance_usd)}</dd></div>}
      </dl>
      <p className="mira-source">Total for your group, from our 2026/27 rates. Quote {quote_id}.</p>
    </Card>
  );
}

type BookingOutcome = { status: string; message: string; next_step: string; booking_ref?: string | null };

export function BookingForm({ quote_id }: Props<"show_booking_form">) {
  const [state, setState] = useState<"idle" | "sending" | "done">("idle");
  const [outcome, setOutcome] = useState<BookingOutcome | null>(null);

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
    const ok = outcome.status === "confirmed";
    return (
      <Card accent={ok ? "leaf" : "sun"} label={ok ? "Booked" : "Not booked yet"}>
        <p className="mira-card__body"><strong>{outcome.message}</strong></p>
        <p className="mira-card__body">{outcome.next_step}</p>
        {!ok && (
          <button className="mira-button mira-button--ghost" onClick={() => setState("idle")}>Try again</button>
        )}
      </Card>
    );
  }

  return (
    <Card accent="leaf" label="Reserve this trip">
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

export function SpecialistHandoff({ message }: Props<"show_specialist_handoff">) {
  return (
    <Card accent="sun" label="Passed to our team">
      <p className="mira-card__body">{message}</p>
      <p className="mira-source">A travel specialist has been notified and will confirm with you.</p>
    </Card>
  );
}

export function SourceList({ sources }: Props<"show_source_list">) {
  return (
    <Card accent="sky" label="Sources">
      <ul className="mira-list">
        {sources.map((s) => (
          <li key={s.source_path}>{s.title} <span className="mira-source">({shortSource(s.source_path)})</span></li>
        ))}
      </ul>
    </Card>
  );
}
