"use client";
// The conversation is the product: a branded header and Mira's chat, full height on any screen.
import { CopilotChat } from "@copilotkit/react-core/v2";

export default function Home() {
  return (
    <div className="shell">
      <header className="topbar">
        <span className="topbar__mark" aria-hidden>◆</span>
        <span className="topbar__name">Ceylon Compass Holidays</span>
        <span className="topbar__tag">Plan, price and book with Mira</span>
      </header>
      <main className="chat">
        <CopilotChat
          agentId="mira"
          labels={{
            modalHeaderTitle: "Mira",
            welcomeMessageText:
              "Hi, I'm Mira. I can find a tour, give you an exact price and book it. Are you after a day tour or a longer trip?",
            chatInputPlaceholder: "Try: Sigiriya day tour for 2 adults on 10 January 2027",
          }}
        />
      </main>
    </div>
  );
}
