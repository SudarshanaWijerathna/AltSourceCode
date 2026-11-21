"use client";
// The conversation is the product: a branded header, a welcome-back card for returning visitors,
// and Mira's chat, full height on any screen.
import { CopilotChat, useAgent } from "@copilotkit/react-core/v2";
import { useEffect, useRef, useState } from "react";

import { useCardGroups } from "@/lib/useCardGroups";
import { useCentredPrompt } from "@/lib/useCentredPrompt";
import { useMarkFlight } from "@/lib/useMarkFlight";
import { usePromptBarShape } from "@/lib/usePromptBarShape";
import { party, WelcomeBack } from "@/components/WelcomeBack";
import { forgetVisitor, visitorThread, type Welcome } from "@/lib/visitor";

const NEW_VISITOR =
  "Hi, I'm Mira. I can find a tour, give you an exact price and book it. Are you after a day tour or a longer trip?";


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


/** Opening line before the conversation starts.
 *  New visitor: the start screen - Mira's mark and greeting centred, the prompt bar lifted under
 *  them; on the first prompt the mark flies to the reply and the bar slides down.
 *  Returning visitor: no start screen - the greeting shows as an ordinary Mira message at the top
 *  and the prompt bar stays at the bottom (no animation). */
function Greeting({ text, centred }: { text: string; centred: boolean }) {
  const { agent } = useAgent({ agentId: "mira" });
  const empty = agent.messages.length === 0;
  const mark = useRef<HTMLImageElement>(null);
  useCentredPrompt(empty && centred);
  useMarkFlight(empty && centred, mark);
  if (!empty) return null;
  if (!centred) {
    return (
      <div className="greeting" role="status">
        <p>{text}</p>
      </div>
    );
  }
  return (
    <div className="intro" role="status">
      <img ref={mark} className="intro__mark" src="/brand/mira.svg" alt="Mira" width={120} height={71} />
      <p>{text}</p>
    </div>
  );
}

export default function Home() {
  const [thread, setThread] = useState<{ visitorId: string; threadId: string } | null>(null);
  const [welcome, setWelcome] = useState<Welcome | null>(null);
  const { narrow } = usePromptBarShape();
  useCardGroups(Boolean(thread && welcome));

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
        <img className="topbar__logo" src="/brand/CeylonCompassHolidays.svg" alt="" width={34} height={34} />
        <span className="topbar__name">Ceylon Compass Holidays</span>
        <span className="topbar__sep" aria-hidden>|</span>
        <span className="topbar__tag">Plan, price and book with Mira</span>
        {welcome?.returning && (
          <button className="topbar__forget" onClick={() => { forgetVisitor(); location.reload(); }}>
            Forget me
          </button>
        )}
      </header>
      <div className="content">
      {welcome?.last_quote && <WelcomeBack q={welcome.last_quote} />}
      <main className="chat">
        {thread && welcome && <Greeting text={welcomeText(welcome)} centred={!welcome.returning} />}
        <p className="chat-note">AI can make mistakes. Please verify important information.</p>
        {thread && welcome && (
          <CopilotChat
            agentId="mira"
            threadId={thread.threadId}
            labels={{
              modalHeaderTitle: "Mira",
              welcomeMessageText: welcomeText(welcome),
              chatInputPlaceholder: narrow
                ? "Ask Mira about a tour…"
                : "Try: Sigiriya day tour for 2 adults on 10 January 2027",
            }}
          />
        )}
      </main>
      </div>
    </div>
  );
}
