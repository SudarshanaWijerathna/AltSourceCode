"use client";
// Decoration: two large outlines of Mira's mark, cut off by the chat box's edges (top left and
// bottom right). Desktop only; hidden from screen readers and never in the way of clicks.
import { MIRA_LOGO_PATH } from "@/components/MiraMark";

function Outline({ className }: { className: string }) {
  return (
    <svg className={`logo-decor ${className}`} viewBox="-2 -2 455.37 270.88" aria-hidden focusable="false">
      <path d={MIRA_LOGO_PATH} fill="none" stroke="currentColor" strokeWidth={0.75} vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

export function LogoDecor() {
  return (
    <>
      <Outline className="logo-decor--left" />
      <Outline className="logo-decor--right" />
    </>
  );
}
