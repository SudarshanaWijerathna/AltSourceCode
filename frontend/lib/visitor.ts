"use client";
// A pseudonymous visitor id (random, no personal data) kept in localStorage so Mira can greet a
// returning visitor with their last quote. Each browser tab session gets a new conversation thread:
// threadId = "<visitor>.<session>" — the backend reads the visitor from it (mira/visitors.py).

const rand = (n: number) =>
  Array.from(crypto.getRandomValues(new Uint8Array(n)), (b) => b.toString(16).padStart(2, "0")).join("");

function stored(storage: Storage, key: string, make: () => string): string {
  try {
    const existing = storage.getItem(key);
    if (existing) return existing;
    const value = make();
    storage.setItem(key, value);
    return value;
  } catch {
    return make(); // private mode / blocked storage: still works, just not remembered
  }
}

export function visitorThread(): { visitorId: string; threadId: string } {
  const visitorId = stored(localStorage, "mira.visitor", () => `v-${rand(8)}`);
  const sessionId = stored(sessionStorage, "mira.session", () => `s${rand(6)}`);
  return { visitorId, threadId: `${visitorId}.${sessionId}` };
}

export function forgetVisitor() {
  try {
    localStorage.removeItem("mira.visitor");
    sessionStorage.removeItem("mira.session");
  } catch {
    /* ignore */
  }
}

export type LastQuote = {
  enquiry_id: string;
  tour_id: string;
  tour_title: string | null;
  start_date: string;
  adults: number;
  children: number;
  infants: number;
  still_valid: boolean;
  price_usd: string | null;
  deposit_usd: string | null;
  booked: boolean;
};

export type Welcome = { returning: boolean; last_quote?: LastQuote | null; profile?: Record<string, unknown> };
