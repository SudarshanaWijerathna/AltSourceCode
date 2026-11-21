"use client";
// Reports whether the screen is narrow, so the page can use a prompt placeholder that fits on one
// line on phones. The prompt bar's one-line vs two-row layout is left entirely to CopilotKit (its
// own measurement decides when to wrap); globals.css only styles the layout it picks. An earlier
// version forced the layout from here and fought CopilotKit's own logic, which made the bar
// flicker at the wrap point.
import { useEffect, useState } from "react";

export function usePromptBarShape() {
  const [narrow, setNarrow] = useState(false);
  useEffect(() => {
    const mq = window.matchMedia("(max-width: 640px)");
    const onChange = () => setNarrow(mq.matches);
    onChange();
    mq.addEventListener("change", onChange);
    return () => mq.removeEventListener("change", onChange);
  }, []);
  return { narrow };
}
