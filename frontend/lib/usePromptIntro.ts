"use client";
// Start screen: the prompt bar's entrance, played alongside Mira's mark being drawn.
//   1. pop:    the bar appears as a circle (66px, the pill's height) holding only the send arrow;
//   2. expand: it widens to full width from the centre, the arrow riding its right edge;
//   3. text:   the placeholder fades in left to right, character by character.
// CopilotKit owns the bar, so this only animates it (Web Animations) and restores every inline
// style afterwards. The placeholder is faded in by an overlay laid exactly over the real one, which
// is put back when the overlay is done (or the moment the traveller starts typing).
import { useEffect } from "react";

const POP = 520;        // ms
const EXPAND = 1040;    // ms, starts after the pop
const TEXT_AT = POP + 240; // ms: fades in while the bar widens, moving left with its edge
const MS_PER_CHAR = 18; // per character
const CHAR_FADE = 520;  // each character's fade
const EASE = "cubic-bezier(.2, .8, .2, 1)";

function play(input: HTMLElement): () => void {
  const grid = input.firstElementChild as HTMLElement | null;
  const ta = input.querySelector("textarea");
  if (!grid || !ta) return () => {};

  const width = input.getBoundingClientRect().width;
  const height = input.getBoundingClientRect().height;
  const gs = getComputedStyle(grid);
  const placeholder = ta.getAttribute("placeholder") ?? "";

  // Hold the real placeholder back; the overlay fades it in.
  ta.setAttribute("placeholder", "");
  Object.assign(input.style, { marginInline: "auto", overflow: "hidden" });

  const anims: Animation[] = [
    input.animate(
      [{ transform: "scale(.2)", opacity: 0 }, { transform: "scale(1.06)", opacity: 1, offset: 0.7 }, { transform: "scale(1)", opacity: 1 }],
      { duration: POP, easing: "ease-out", fill: "backwards" },
    ),
    input.animate([{ width: `${height}px` }, { width: `${width}px` }],
      { duration: EXPAND, delay: POP, easing: EASE, fill: "backwards" }),
    // At circle size the arrow must sit in the middle: the side padding matches the right one
    // and the empty columns' gaps collapse, then both ease back with the widening.
    grid.animate(
      [{ paddingLeft: gs.paddingRight, columnGap: "0px" }, { paddingLeft: gs.paddingLeft, columnGap: gs.columnGap }],
      { duration: EXPAND, delay: POP, easing: EASE, fill: "backwards" },
    ),
  ];

  // Overlay: same font, position and colour as the textarea's placeholder.
  const ts = getComputedStyle(ta);
  const overlay = document.createElement("span");
  overlay.setAttribute("aria-hidden", "true");
  overlay.className = "prompt-intro__text";
  Object.assign(overlay.style, {
    left: `${ta.offsetLeft + parseFloat(ts.paddingLeft) + parseFloat(ts.borderLeftWidth)}px`,
    top: `${ta.offsetTop + parseFloat(ts.paddingTop) + parseFloat(ts.borderTopWidth)}px`,
    right: `${parseFloat(ts.paddingRight)}px`,
    font: ts.font, lineHeight: ts.lineHeight, letterSpacing: ts.letterSpacing,
    color: getComputedStyle(ta, "::placeholder").color,
  });
  [...placeholder].forEach((ch, i) => {
    const s = document.createElement("span");
    s.className = "typed__ch";
    s.textContent = ch;
    s.style.animationDelay = `${TEXT_AT + i * MS_PER_CHAR}ms`;
    s.style.animationDuration = `${CHAR_FADE}ms`;
    overlay.appendChild(s);
  });
  ta.parentElement?.appendChild(overlay);

  let done = false;
  const finish = () => {
    if (done) return;
    done = true;
    anims.forEach((a) => a.cancel());
    overlay.remove();
    input.style.marginInline = "";
    input.style.overflow = "";
    // React may have set a new placeholder meanwhile (e.g. the phone/desktop wording changed).
    if (!ta.getAttribute("placeholder")) ta.setAttribute("placeholder", placeholder);
    ta.removeEventListener("input", finish);
  };
  ta.addEventListener("input", finish); // typing early: show the real bar at once
  const timer = setTimeout(finish, TEXT_AT + placeholder.length * MS_PER_CHAR + CHAR_FADE + 20);
  return () => {
    clearTimeout(timer);
    finish();
  };
}

export function usePromptIntro(active: boolean) {
  useEffect(() => {
    if (!active || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
    const chat = document.querySelector(".chat");
    if (!chat) return;
    let stop: (() => void) | null = null;
    const start = () => {
      const input = chat.querySelector<HTMLElement>(".copilotKitInput");
      if (stop || !input?.querySelector("textarea")) return;
      stop = play(input);
      mo.disconnect();
    };
    const mo = new MutationObserver(start); // the bar mounts once the thread is ready
    mo.observe(chat, { childList: true, subtree: true });
    start();
    return () => {
      mo.disconnect();
      stop?.();
    };
  }, [active]);
}
