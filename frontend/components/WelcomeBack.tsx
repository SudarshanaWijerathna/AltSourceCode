"use client";
// Welcome-back notification for returning visitors (shown above the chat, and in the /cards gallery).
import { useState } from "react";

import { usd } from "@/lib/catalog";
import type { LastQuote } from "@/lib/visitor";

export function party(q: LastQuote) {
  const parts = [`${q.adults} adult${q.adults === 1 ? "" : "s"}`];
  if (q.children) parts.push(`${q.children} child${q.children === 1 ? "" : "ren"}`);
  if (q.infants) parts.push(`${q.infants} infant${q.infants === 1 ? "" : "s"}`);
  return parts.join(", ");
}

export function WelcomeBack({ q }: { q: LastQuote }) {
  // Closing hides the card for this page view only; it shows again on the next load.
  const [closed, setClosed] = useState(false);
  if (closed) return null;
  const close = () => setClosed(true);
  return (
    <aside className="welcome mira-card" style={{ ["--accent" as string]: "var(--accent-leaf)" }}>
      <button className="welcome__close" onClick={close} aria-label="Close welcome back message">×</button>
      <p className="mira-card__label">Welcome back · your last quote</p>
      <p className="welcome__trip"><strong>{q.tour_title ?? q.tour_id}</strong> · <span className="nowrap">{party(q)}</span> · <span className="nowrap">from {q.start_date}</span></p>
      {q.still_valid && q.price_usd ? (
        <p className="welcome__price"><span className="nowrap">{usd(Number(q.price_usd))} total</span> · <span className="nowrap">deposit {usd(Number(q.deposit_usd))}</span></p>
      ) : (
        <p className="mira-source">Prices change with dates and rates, so ask Mira to re-check it.</p>
      )}
    </aside>
  );
}
