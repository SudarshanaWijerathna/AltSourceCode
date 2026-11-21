"use client";
// When the first prompt is sent, the large centred Mira mark shrinks and flies to the small mark of
// Mira's first response (the "thinking" dot's mark, or the reply's if it arrives first). FLIP: the
// big mark's last position is remembered; a fixed-position copy animates from there to the target;
// the target mark stays hidden (.chat.mira-flying) until the copy lands. 600ms, deliberately longer
// than the brand pack's 200ms rule so the start-to-conversation change is easy to follow.
import { type RefObject, useLayoutEffect, useRef } from "react";

const DURATION = 600; // ms; matches the prompt bar slide (.prompt-wrap--animate)
const PHONE = "(max-width: 520px)";

type Box = { left: number; top: number; width: number; height: number };

/** Where the small mark of Mira's first response is drawn (matches the ::before rules in globals.css). */
function targetBox(chat: Element): Box | null {
  const phone = matchMedia(PHONE).matches;
  const [w, h] = phone ? [32, 19] : [36, 22];
  const thinking = chat.querySelector<HTMLElement>('div:has(> [data-testid="copilot-loading-cursor"])');
  if (thinking) {
    const r = thinking.getBoundingClientRect();
    return { left: r.left, top: phone ? r.top : r.top + r.height / 2 - h / 2, width: w, height: h };
  }
  const reply = chat.querySelector<HTMLElement>(".copilotKitAssistantMessage");
  if (reply) {
    const r = reply.getBoundingClientRect();
    return { left: r.left, top: phone ? r.top : r.top + 23, width: w, height: h };
  }
  return null;
}

export function useMarkFlight(empty: boolean, mark: RefObject<Element | null>) {
  const last = useRef<Box | null>(null);
  const wasEmpty = useRef(empty);

  // While the start screen shows, keep the big mark's position up to date.
  useLayoutEffect(() => {
    if (!empty) return;
    const save = () => {
      const r = mark.current?.getBoundingClientRect();
      if (r && r.width) last.current = { left: r.left, top: r.top, width: r.width, height: r.height };
    };
    save();
    const t = setInterval(save, 250); // the prompt bar placement can nudge layout after mount
    window.addEventListener("resize", save);
    return () => {
      save();
      clearInterval(t);
      window.removeEventListener("resize", save);
    };
  });

  useLayoutEffect(() => {
    const leavingStart = wasEmpty.current && !empty;
    wasEmpty.current = empty;
    const from = last.current;
    const chat = document.querySelector<HTMLElement>(".chat");
    if (!leavingStart || !from || !chat || matchMedia("(prefers-reduced-motion: reduce)").matches) return;

    const ghost = document.createElement("img");
    ghost.src = "/brand/mira.svg";
    ghost.alt = "";
    ghost.className = "mira-ghost";
    Object.assign(ghost.style, {
      left: `${from.left}px`, top: `${from.top}px`, width: `${from.width}px`, height: `${from.height}px`,
    });
    document.body.appendChild(ghost);
    chat.classList.add("mira-flying");

    let cancelled = false;
    let frame = 0;
    const started = performance.now();
    const finish = () => {
      ghost.remove();
      chat.classList.remove("mira-flying");
    };
    const fly = () => {
      if (cancelled) return;
      const to = targetBox(chat);
      if (!to) {
        if (performance.now() - started > 3000) return finish(); // no response yet: just drop the ghost
        frame = requestAnimationFrame(fly);
        return;
      }
      const scale = to.width / from.width;
      ghost.animate(
        [
          { transform: "translate(0, 0) scale(1)" },
          { transform: `translate(${to.left - from.left}px, ${to.top - from.top}px) scale(${scale})` },
        ],
        { duration: DURATION, easing: "cubic-bezier(.2, .8, .2, 1)", fill: "forwards" },
      ).finished.then(finish, finish);
    };
    frame = requestAnimationFrame(fly);
    return () => {
      cancelled = true;
      cancelAnimationFrame(frame);
    };
  }, [empty]);
}
