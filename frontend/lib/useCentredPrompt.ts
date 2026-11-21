"use client";
// Start screen (wider than a phone): while the conversation is empty, lift CopilotKit's prompt bar from the bottom of the
// chat to just below its vertical centre (under Mira's centred greeting). When the first message is
// sent the lift is removed and the bar slides back down (CSS transition on .prompt-wrap).
import { useLayoutEffect } from "react";

const GAP_BELOW_CENTRE = 8; // px between the chat's vertical centre and the top of the prompt bar
// Phones keep the bar at the bottom even on the start screen: easier to reach one-handed.
const PHONE = "(max-width: 520px)";

function promptWrap(chat: Element): HTMLElement | null {
  const input = chat.querySelector<HTMLElement>(".copilotKitInput");
  // The wrapper that holds the bar and the "AI can make mistakes" line.
  return (input?.closest<HTMLElement>('[class*="z-20"]') ?? input?.parentElement) || null;
}

/** CopilotKit's "AI can make mistakes…" line lives inside the moving wrapper, so it is kept invisible
 *  (holding its space) and the page renders the same line, fixed at the bottom (.chat-note). */
function disclaimer(wrap: HTMLElement): HTMLElement | null {
  return [...wrap.querySelectorAll<HTMLElement>("*")].find(
    (el) => !el.querySelector(".copilotKitInput") && !el.closest(".copilotKitInput") && /mistakes/i.test(el.textContent ?? "")
      && ![...el.children].some((c) => /mistakes/i.test(c.textContent ?? "")),
  ) ?? null;
}

export function useCentredPrompt(empty: boolean) {
  useLayoutEffect(() => {
    const chat = document.querySelector<HTMLElement>(".chat");
    if (!chat) return;
    let frame = 0;

    const apply = () => {
      const wrap = promptWrap(chat);
      if (!wrap) return;
      wrap.classList.add("prompt-wrap");
      const note = disclaimer(wrap);
      note?.classList.add("prompt-note");
      if (!empty) {
        wrap.dataset.lift = "0";
        wrap.style.transform = "";
        return;
      }
      // Layout position (offsetTop ignores transforms), so measuring mid-animation can't compound.
      let naturalTop = 0;
      for (let e: HTMLElement | null = wrap; e && e !== chat; e = e.offsetParent as HTMLElement | null) naturalTop += e.offsetTop;
      const lift = matchMedia(PHONE).matches
        ? 0
        : Math.max(0, Math.round(naturalTop - (chat.clientHeight / 2 + GAP_BELOW_CENTRE)));
      // The first placement is instant: CopilotKit's own inline transition would otherwise slide
      // the bar up from the bottom as the page opens. Later moves animate (.prompt-wrap--animate).
      const first = !wrap.classList.contains("prompt-wrap--animate");
      if (first) wrap.classList.add("prompt-wrap--placing");
      wrap.dataset.lift = String(lift);
      wrap.style.transform = lift ? `translateY(-${lift}px)` : "";
      if (first) {
        void wrap.offsetHeight; // commit the placement before transitions return
        wrap.classList.remove("prompt-wrap--placing");
      }
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => wrap.classList.add("prompt-wrap--animate"));
    };

    apply();
    const mutations = new MutationObserver(() => {
      const wrap = promptWrap(chat);
      if (wrap && !wrap.dataset.lift) apply();
    });
    mutations.observe(chat, { childList: true, subtree: true }); // the input mounts after the thread is ready
    window.addEventListener("resize", apply);
    const resize = new ResizeObserver(() => apply()); // e.g. the welcome-back card is closed
    resize.observe(chat);
    return () => {
      resize.disconnect();
      mutations.disconnect();
      window.removeEventListener("resize", apply);
      cancelAnimationFrame(frame);
    };
  }, [empty]);
}
