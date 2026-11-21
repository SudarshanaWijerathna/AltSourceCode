"use client";
// The conversation is the product: a branded header, a welcome-back card for returning visitors,
// and Mira's chat, full height on any screen.
import { CopilotChat, useAgent } from "@copilotkit/react-core/v2";
import { useEffect, useState } from "react";

import { usd } from "@/lib/catalog";
import { forgetVisitor, type LastQuote, visitorThread, type Welcome } from "@/lib/visitor";

const NEW_VISITOR =
  "Hi, I'm Mira. I can find a tour, give you an exact price and book it. Are you after a day tour or a longer trip?";

function party(q: LastQuote) {
  const parts = [`${q.adults} adult${q.adults === 1 ? "" : "s"}`];
  if (q.children) parts.push(`${q.children} child${q.children === 1 ? "" : "ren"}`);
  if (q.infants) parts.push(`${q.infants} infant${q.infants === 1 ? "" : "s"}`);
  return parts.join(", ");
}

function welcomeText(w: Welcome | null): string {
  const q = w?.last_quote;
  if (!w?.returning) return NEW_VISITOR;
  if (!q) return "Welcome back. I remember what you told me last time. Where would you like to pick up?";
  const trip = `${q.tour_title ?? q.tour_id} for ${party(q)} from ${q.start_date}`;
  if (q.booked) return `Welcome back. Your ${trip} is booked. Can I help with anything else?`;
  return q.still_valid
    ? `Welcome back. Last time you looked at the ${trip}. Would you like to book it, or change anything?`
    : `Welcome back. Last time you looked at the ${trip}. I'll check the price again for you. Shall I?`;
}

function WelcomeBack({ q }: { q: LastQuote }) {
  return (
    <aside className="welcome mira-card" style={{ ["--accent" as string]: "var(--accent-leaf)" }}>
      <p className="mira-card__label">Welcome back · your last quote</p>
      <p className="welcome__trip"><strong>{q.tour_title ?? q.tour_id}</strong> · {party(q)} · from {q.start_date}</p>
      {q.still_valid && q.price_usd ? (
        <p className="welcome__price">{usd(Number(q.price_usd))} total · deposit {usd(Number(q.deposit_usd))}</p>
      ) : (
        <p className="mira-source">Prices change with dates and rates, so ask Mira to re-check it.</p>
      )}
    </aside>
  );
}

/** Mira's opening line, shown until the conversation starts. */
function Greeting({ text }: { text: string }) {
  const { agent } = useAgent({ agentId: "mira" });
  if (agent.messages.length > 0) return null;
  return (
    <div className="greeting" role="status">
      <span className="greeting__name">Mira</span>
      <p>{text}</p>
    </div>
  );
}

export default function Home() {
  const [thread, setThread] = useState<{ visitorId: string; threadId: string } | null>(null);
  const [welcome, setWelcome] = useState<Welcome | null>(null);

  useEffect(() => {
    const t = visitorThread();
    setThread(t);
    fetch(`/backend/visitor/${t.visitorId}/welcome`)
      .then((r) => (r.ok ? r.json() : { returning: false }))
      .then(setWelcome)
      .catch(() => setWelcome({ returning: false }));
  }, []);

  return (
    <div className="shell">
      <header className="topbar">
        <span className="topbar__mark" aria-hidden>◆</span>
        <span className="topbar__name">Ceylon Compass Holidays</span>
        <span className="topbar__tag">Plan, price and book with Mira</span>
        {welcome?.returning && (
          <button className="topbar__forget" onClick={() => { forgetVisitor(); location.reload(); }}>
            Forget me
          </button>
        )}
      </header>
      {welcome?.last_quote && <WelcomeBack q={welcome.last_quote} />}
      <main className="chat">
        {thread && welcome && <Greeting text={welcomeText(welcome)} />}
        {thread && welcome && (
          <CopilotChat
            agentId="mira"
            threadId={thread.threadId}
            labels={{
              modalHeaderTitle: "Mira",
              welcomeMessageText: welcomeText(welcome),
              chatInputPlaceholder: "Try: Sigiriya day tour for 2 adults on 10 January 2027",
            }}
          />
        )}
      </main>
    </div>
  );
}
