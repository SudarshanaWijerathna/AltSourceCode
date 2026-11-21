"use client";
// Mira's mark (the merged, gradient-filled logo from /brand/mira.svg), drawn in place when a new
// conversation starts. The logo itself is never altered: a mask reveals it along the pen path of
// its five parts (mira_logo.ai): (1) up the first stroke, (2) down its link, (3) up the second
// stroke, (4) down its link, (5) the dot. Each part is a stroke animated with stroke-dashoffset;
// with reduced motion the mark simply shows.
import { forwardRef, useId } from "react";

export const MIRA_LOGO_PATH =
  "M451.37,219.64c0,12.08-4.61,24.18-13.83,33.4-9.23,9.22-21.31,13.84-33.41,13.84s-24.18-4.62-33.4-13.84c-15.66-15.66-18.03-39.58-7.1-57.73l49.77-96.58-154.31,154.31c-18.45,18.45-48.36,18.45-66.81,0-16.3-16.31-18.19-41.56-5.68-59.94l48.93-94.95L80.64,253.04c-18.45,18.45-48.35,18.45-66.8,0s-18.45-48.36,0-66.8L186.24,13.84c18.44-18.45,48.35-18.45,66.8,0,9.23,9.22,13.84,21.32,13.84,33.4,0,10.23-3.3,20.47-9.92,28.96l-48.21,93.57L364.68,13.84c18.45-18.45,48.36-18.45,66.81,0,9.22,9.22,13.84,21.32,13.84,33.4,0,10.62-3.56,21.24-10.69,29.91l-51.64,100.23c6.63-3.32,13.88-4.98,21.13-4.98,12.1,0,24.18,4.62,33.41,13.84,9.22,9.22,13.83,21.31,13.83,33.4Z";

// Pen path in logo units (viewBox 451.37 x 266.88; the strokes are 94.5 wide, the links ~20).
// [path, mask stroke width, start ms, duration ms]
const STROKES: [string, number, number, number][] = [
  ["M47.24,219.64 L219.64,47.24", 98, 0, 210],     // 1 -> 2: first stroke
  ["M266.8,47.24 L178,219.64", 34, 210, 100],      // 2 -> 3: its link
  ["M225.69,219.64 L398.08,47.24", 98, 310, 210],  // 3 -> 4: second stroke
  ["M445,47.24 L356.2,219.64", 34, 520, 100],     // 4 -> 5: its link
];
const DOT = { cx: 404.13, cy: 219.64, r: 50, start: 600, duration: 130 }; // 5: the dot


export const MiraMark = forwardRef<SVGSVGElement, { className?: string; width?: number }>(
  function MiraMark({ className, width = 120 }, ref) {
    const id = useId().replace(/:/g, "");
    return (
      <svg ref={ref} className={className} viewBox="0 0 451.37 266.88" width={width}
           height={Math.round((width * 266.88) / 451.37)} role="img" aria-label="Mira">
        <defs>
          <linearGradient id={`${id}g`} x1="0" y1="133.44" x2="451.37" y2="133.44" gradientUnits="userSpaceOnUse">
            <stop offset="0" stopColor="#52c1b8" />
            <stop offset="1" stopColor="#99d7d6" />
          </linearGradient>
          <mask id={`${id}m`} maskUnits="userSpaceOnUse" x="-20" y="-20" width="492" height="307">
            {STROKES.map(([d, w, start, duration]) => (
              <path key={d} className="mira-mark__pen" d={d} pathLength={1} stroke="#fff" strokeWidth={w}
                    strokeLinecap="round" fill="none"
                    style={{ animationDelay: `${start}ms`, animationDuration: `${duration}ms` }} />
            ))}
            <circle className="mira-mark__dot" cx={DOT.cx} cy={DOT.cy} r={DOT.r} fill="#fff"
                    style={{ animationDelay: `${DOT.start}ms`, animationDuration: `${DOT.duration}ms`,
                             transformOrigin: `${DOT.cx}px ${DOT.cy}px` }} />
          </mask>
        </defs>
        <path d={MIRA_LOGO_PATH} fill={`url(#${id}g)`} mask={`url(#${id}m)`} />
      </svg>
    );
  },
);
