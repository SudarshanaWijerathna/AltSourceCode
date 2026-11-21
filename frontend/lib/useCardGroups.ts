"use client";
// Groups the cards of each Mira reply on one light panel (#F6F8FC). CopilotKit renders every card as
// a direct child of the reply (no wrapper we could style), so the panel is drawn by the reply's
// ::after (globals.css) from measured positions: --cards-top/left/width/height, padding included.
// Re-measured whenever cards stream in or the layout changes.
import { useEffect } from "react";

const PAD = 12; // px of panel around the cards

function measure(chat: Element) {
  for (const msg of chat.querySelectorAll<HTMLElement>(".copilotKitAssistantMessage")) {
    const cards = [...msg.children].filter((c): c is HTMLElement => c.classList.contains("mira-card"));
    if (!cards.length) {
      if (msg.dataset.cards) delete msg.dataset.cards;
      continue;
    }
    const top = Math.min(...cards.map((c) => c.offsetTop));
    const bottom = Math.max(...cards.map((c) => c.offsetTop + c.offsetHeight));
    const left = Math.min(...cards.map((c) => c.offsetLeft));
    const right = Math.max(...cards.map((c) => c.offsetLeft + c.offsetWidth));
    const vars = {
      "--cards-top": `${top - PAD}px`, "--cards-left": `${left - PAD}px`,
      "--cards-width": `${right - left + 2 * PAD}px`, "--cards-height": `${bottom - top + 2 * PAD}px`,
    };
    for (const [k, v] of Object.entries(vars)) if (msg.style.getPropertyValue(k) !== v) msg.style.setProperty(k, v);
    msg.dataset.cards = String(cards.length);
  }
}

export function useCardGroups(active: boolean) {
  useEffect(() => {
    if (!active) return;
    const chat = document.querySelector(".chat");
    if (!chat) return;
    let frame = 0;
    const schedule = () => {
      cancelAnimationFrame(frame);
      frame = requestAnimationFrame(() => measure(chat));
    };
    const mutations = new MutationObserver(schedule);
    mutations.observe(chat, { childList: true, subtree: true });
    const resize = new ResizeObserver(schedule); // card heights change (e.g. booking form -> result)
    resize.observe(chat);
    const watchCards = () => chat.querySelectorAll(".mira-card").forEach((c) => resize.observe(c));
    const cardMutations = new MutationObserver(watchCards);
    cardMutations.observe(chat, { childList: true, subtree: true });
    window.addEventListener("resize", schedule);
    watchCards();
    schedule();
    return () => {
      mutations.disconnect();
      cardMutations.disconnect();
      resize.disconnect();
      window.removeEventListener("resize", schedule);
      cancelAnimationFrame(frame);
    };
  }, [active]);
}
